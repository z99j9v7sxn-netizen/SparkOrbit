/** 伴学 next_actions 类型化执行（真开路径/资源流，而非只重发文案）。 */
import { generateLearningPath, startResourceGeneration, type ResourceKind } from '../api/learnExtras';
import { setPendingResourceStream } from './pendingResourceStream';

export type NextAction = {
  type?: string;
  label?: string;
  status?: string;
  error?: string;
  run_id?: string;
  path_id?: string;
  planet_slug?: string;
  kinds?: string[];
  tool_name?: string;
  title?: string;
};

export type NextActionContext = {
  planetSlug?: string;
  /** 切到费曼模式 */
  onFeynman?: () => void;
  /** 预填提问并发送（兜底） */
  onAsk?: (text: string) => void;
  /** 提示文案 */
  onTip?: (msg: string) => void;
};

function openDock(dock: string, extra?: Record<string, unknown>) {
  window.dispatchEvent(
    new CustomEvent('sparkorbit:open-dock', {
      detail: { dock, ...extra },
    }),
  );
}

function startResourceStream(detail: {
  runId: string;
  planetSlug?: string;
  kinds?: string[];
}) {
  openDock('resources');
  // 先写入 pending，再广播；ResourceStudio 挂载后会 takePending，避免竞态丢事件
  setPendingResourceStream(detail);
}

export async function executeNextAction(action: NextAction, ctx: NextActionContext = {}): Promise<void> {
  const type = (action.type || '').trim();
  const planet = action.planet_slug || ctx.planetSlug || '';

  if (action.status === 'error' && action.error) {
    ctx.onTip?.(action.error);
  }

  if (type === 'open_path' || type === 'generate_path') {
    openDock('path');
    if (type === 'generate_path' || !action.path_id) {
      try {
        await generateLearningPath(action.label || '伴学推荐路径');
        ctx.onTip?.('已生成学习路径');
      } catch (e) {
        ctx.onTip?.(e instanceof Error ? e.message : '生成路径失败');
      }
    } else {
      ctx.onTip?.(action.title ? `已打开路径「${action.title}」` : '已打开学习路径');
    }
    return;
  }

  if (type === 'stream_resources') {
    const runId = action.run_id || '';
    if (!runId) {
      ctx.onTip?.('缺少资源 run_id');
      return;
    }
    startResourceStream({
      runId,
      planetSlug: planet,
      kinds: action.kinds,
    });
    ctx.onTip?.('已进入资源工坊，正在拉取生成流…');
    return;
  }

  if (type === 'generate_deck' || type === 'generate_quiz' || type === 'generate_resource') {
    if (!planet) {
      ctx.onTip?.('请先选择知识点行星');
      return;
    }
    const kinds = (action.kinds?.length
      ? action.kinds
      : type === 'generate_quiz'
        ? ['quiz']
        : type === 'generate_deck'
          ? ['deck']
          : ['doc', 'mindmap', 'quiz']) as ResourceKind[];
    try {
      const { run_id } = await startResourceGeneration(planet, kinds, action.label || '');
      startResourceStream({ runId: run_id, planetSlug: planet, kinds });
      ctx.onTip?.('已启动资源生成');
    } catch (e) {
      ctx.onTip?.(e instanceof Error ? e.message : '启动资源生成失败');
    }
    return;
  }

  if (type === 'feynman') {
    ctx.onFeynman?.();
    ctx.onAsk?.('请用费曼法引导我讲解当前知识点');
    return;
  }

  if (type === 'need_planet') {
    ctx.onTip?.(action.label || '请先选择行星');
    return;
  }

  if (type === 'rest') {
    ctx.onTip?.(action.label || '先休息一下再学');
    return;
  }

  // 兜底：把 label 当新提问
  const label = (action.label || type).trim();
  if (label) ctx.onAsk?.(label);
}
