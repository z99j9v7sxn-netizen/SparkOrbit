/**
 * 讯飞虚拟人按需连接封装。
 * 计费按 WebSocket 展示时长：仅 enable() 时 start，disable()/卸载时 stop+destroy。
 */
import { nextTick, onBeforeUnmount, ref, shallowRef } from 'vue';
import AvatarPlatform, { PlayerEvents, SDKEvents } from '@avatar-sdk';
import { fetchVmsSession, type VmsSession } from '../api/vms';

export type VmsStatus = 'idle' | 'connecting' | 'live' | 'error';

export function useAvatarVms() {
  const enabled = ref(false);
  const status = ref<VmsStatus>('idle');
  const statusText = ref('虚拟人未连接（不计费）');
  const error = ref('');
  const needGesture = ref(false);
  const session = shallowRef<VmsSession | null>(null);

  let platform: InstanceType<typeof AvatarPlatform> | null = null;
  let idleTimer: ReturnType<typeof setTimeout> | null = null;
  let idleSec = 90;

  function clearIdle() {
    if (idleTimer) {
      clearTimeout(idleTimer);
      idleTimer = null;
    }
  }

  function bumpIdle() {
    clearIdle();
    if (!enabled.value || status.value !== 'live') return;
    idleTimer = setTimeout(() => {
      void disable('空闲超时，已断开虚拟人以节省时长');
    }, Math.max(30, idleSec) * 1000);
  }

  function teardown() {
    clearIdle();
    needGesture.value = false;
    try {
      platform?.stop();
    } catch {
      /* ignore */
    }
    try {
      platform?.destroy();
    } catch {
      /* ignore */
    }
    platform = null;
  }

  /** 等容器真正有宽高后再挂播放器，避免黑屏 */
  async function waitForLayout(wrapper: HTMLDivElement) {
    await nextTick();
    await new Promise<void>((r) => requestAnimationFrame(() => requestAnimationFrame(() => r())));
    for (let i = 0; i < 12; i += 1) {
      const w = wrapper.clientWidth;
      const h = wrapper.clientHeight;
      if (w >= 80 && h >= 80) return;
      await new Promise((r) => setTimeout(r, 50));
    }
    throw new Error('虚拟人容器尺寸为 0，请重试开启');
  }

  function styleWrapper(wrapper: HTMLDivElement) {
    wrapper.style.position = 'relative';
    wrapper.style.overflow = 'hidden';
    wrapper.style.background = '#0b1220';
    // 必须有明确 height，SDK 子节点 height:100% 才不会塌成 0（黑屏根因）
    const h = Math.max(wrapper.clientHeight || 0, 360);
    wrapper.style.height = `${h}px`;
    wrapper.style.minHeight = `${h}px`;
    wrapper.style.width = '100%';
  }

  function hardenPlayerDom(wrapper: HTMLDivElement) {
    const apply = () => {
      const box = wrapper.querySelector('#xvideo') as HTMLElement | null;
      if (box) {
        box.style.width = '100%';
        box.style.height = '100%';
        box.style.minHeight = '360px';
        box.style.position = 'relative';
      }
      wrapper.querySelectorAll('video, canvas').forEach((el) => {
        const node = el as HTMLElement;
        node.style.width = '100%';
        node.style.height = '100%';
        node.style.objectFit = 'contain';
        node.style.background = '#0b1220';
      });
    };
    apply();
    // SDK 异步插入节点后再刷一次
    window.setTimeout(apply, 300);
    window.setTimeout(apply, 1200);
  }

  async function enable(wrapper: HTMLDivElement) {
    if (enabled.value && status.value === 'live' && platform) {
      return;
    }
    error.value = '';
    needGesture.value = false;
    status.value = 'connecting';
    statusText.value = '正在连接虚拟人（开始计费）…';
    styleWrapper(wrapper);
    try {
      await waitForLayout(wrapper);
      const sess = await fetchVmsSession();
      session.value = sess;
      idleSec = sess.idleSec || 90;
      teardown();
      status.value = 'connecting';
      const inst = new AvatarPlatform({ useInlinePlayer: true });
      platform = inst;
      inst.setApiInfo({
        appId: sess.appId,
        apiKey: sess.apiKey,
        apiSecret: sess.apiSecret,
        sceneId: sess.sceneId,
        serverUrl: sess.serverUrl,
      });
      // alpha:0 不透明；透明通道(alpha:1)在部分浏览器会整片黑屏
      // 竖屏形象，与控制台形象 201293001 常见输出一致
      inst.setGlobalParams({
        stream: { protocol: 'xrtc', alpha: 0, bitrate: 1000000, fps: 25 },
        avatar: {
          avatar_id: sess.avatarId,
          width: 720,
          height: 1280,
          audio_format: 1,
        },
        tts: {
          vcn: sess.vcn,
          speed: 50,
          pitch: 50,
          volume: 100,
        },
        avatar_dispatch: { interactive_mode: 0 },
      });
      inst.on(SDKEvents.connected, () => {
        status.value = 'live';
        statusText.value = '虚拟人已连接（展示中计费）';
        bumpIdle();
      });
      inst.on('stream_start', () => {
        statusText.value = '虚拟人画面推流中…';
      });
      inst.on(SDKEvents.frame_start as string, () => {
        needGesture.value = false;
        statusText.value = '虚拟人已连接（展示中计费）';
      });
      inst.on(SDKEvents.disconnected, () => {
        if (enabled.value) {
          status.value = 'idle';
          statusText.value = '虚拟人已断开';
          enabled.value = false;
        }
      });
      inst.on(SDKEvents.error, (err: unknown) => {
        const msg = err instanceof Error ? err.message : String(err || '虚拟人错误');
        error.value = msg;
        statusText.value = msg;
        status.value = 'error';
      });

      // 先创建 player，再绑事件，最后 start
      const player = inst.createPlayer?.() || inst.player;
      player?.on?.(PlayerEvents.playNotAllowed, () => {
        needGesture.value = true;
        statusText.value = '浏览器拦截自动播放，请点击画面开启';
      });
      player?.on?.(PlayerEvents.play, () => {
        needGesture.value = false;
      });

      await inst.start({ wrapper });
      hardenPlayerDom(wrapper);
      enabled.value = true;
      status.value = 'live';
      statusText.value = '虚拟人已连接（展示中计费）';
      bumpIdle();

      // 主动 resume + 说一句开场，驱动首帧（部分线路静默时黑屏）
      try {
        await player?.resume?.();
      } catch {
        needGesture.value = true;
      }
      hardenPlayerDom(wrapper);
      try {
        await inst.writeText('你好，我是星轨虚拟讲师，已准备好为你讲解。', {
          tts: { vcn: sess.vcn },
          nlp: false,
        });
      } catch {
        /* 开场失败不阻断 */
      }
      bumpIdle();
      hardenPlayerDom(wrapper);    } catch (e) {
      teardown();
      enabled.value = false;
      status.value = 'error';
      error.value = e instanceof Error ? e.message : '虚拟人连接失败';
      statusText.value = error.value;
      throw e;
    }
  }

  async function resumePlayback() {
    needGesture.value = false;
    try {
      await platform?.player?.resume?.();
      statusText.value = '虚拟人已连接（展示中计费）';
    } catch (e) {
      needGesture.value = true;
      error.value = e instanceof Error ? e.message : '无法恢复播放';
    }
  }

  async function disable(reason = '已关闭虚拟人（停止计费）') {
    enabled.value = false;
    teardown();
    status.value = 'idle';
    statusText.value = reason;
  }

  async function speak(text: string) {
    const clean = text.replace(/[#*`>_\[\]()]/g, ' ').replace(/\s+/g, ' ').trim();
    if (!clean || !platform || !enabled.value || status.value !== 'live') return false;
    bumpIdle();
    const vcn = session.value?.vcn || 'x7_langxiao_pro';
    await platform.writeText(clean.slice(0, 800), {
      tts: { vcn },
      nlp: false,
    });
    bumpIdle();
    return true;
  }

  /** 立即打断当前口播（暂停/停止讲解时调用） */
  async function interrupt() {
    if (!platform) return;
    try {
      await platform.interrupt();
    } catch {
      /* 未在播时报错可忽略 */
    }
  }

  onBeforeUnmount(() => {
    void disable('页面关闭，已断开虚拟人');
  });

  return {
    enabled,
    status,
    statusText,
    error,
    needGesture,
    enable,
    disable,
    speak,
    interrupt,
    resumePlayback,
    bumpIdle,
  };
}
