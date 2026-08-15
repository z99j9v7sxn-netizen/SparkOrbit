<script setup lang="ts">
import { ref, watch } from 'vue';
import { downloadVaultZip, updateVaultName, type VaultOpenHint } from '../../../api/vault';

const props = defineProps<{
  open: boolean;
  hint: VaultOpenHint | null;
}>();

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'updated', hint: VaultOpenHint): void;
  (e: 'status', msg: string): void;
}>();

const step = ref(1);
const customName = ref('');
const launchHint = ref('');
const copying = ref(false);
const savingName = ref(false);
const launchMode = ref<'vault' | 'path'>('vault');

watch(
  () => props.open,
  (v) => {
    if (v) {
      step.value = 1;
      launchHint.value = '';
      customName.value = props.hint?.folder_name || props.hint?.launch_vault_name || props.hint?.vault_name || '';
      launchMode.value = 'vault';
    }
  },
);

async function copyPath() {
  const path = props.hint?.local_path || '';
  if (!path) {
    emit('status', '暂无本地路径，请改用导出 zip');
    return;
  }
  copying.value = true;
  try {
    await navigator.clipboard.writeText(path);
    emit('status', '已复制本地知识库路径');
    step.value = Math.max(step.value, 2);
  } catch {
    emit('status', '复制失败，请手动选中路径');
  } finally {
    copying.value = false;
  }
}

async function copyFolderName() {
  const name = props.hint?.folder_name || props.hint?.launch_vault_name || '';
  if (!name) return;
  try {
    await navigator.clipboard.writeText(name);
    emit('status', `已复制建议库名：${name}`);
  } catch {
    emit('status', '复制失败');
  }
}

async function onExport() {
  await downloadVaultZip();
  emit('status', '已下载 Vault zip，解压后用 Obsidian「打开文件夹作为库」');
}

/** 用隐藏 iframe 唤起协议，避免整页跳转离开学习站 */
function invokeUri(uri: string) {
  const iframe = document.createElement('iframe');
  iframe.style.display = 'none';
  iframe.src = uri;
  document.body.appendChild(iframe);
  window.setTimeout(() => iframe.remove(), 2500);
}

function launchObsidian() {
  const uri =
    launchMode.value === 'path'
      ? props.hint?.obsidian_uri_by_path
      : props.hint?.obsidian_uri;
  if (!uri) {
    launchHint.value = '暂无唤起地址。请先完成步骤①②，或导出 zip 后在 Obsidian 中打开。';
    return;
  }
  const expected = props.hint?.launch_vault_name || props.hint?.folder_name || props.hint?.vault_name;
  launchHint.value = `正在唤起 Obsidian（库名：${expected}）…`;
  let blurred = false;
  const onBlur = () => {
    blurred = true;
  };
  const onVis = () => {
    if (document.hidden) blurred = true;
  };
  window.addEventListener('blur', onBlur);
  document.addEventListener('visibilitychange', onVis);
  invokeUri(uri);
  window.setTimeout(() => {
    window.removeEventListener('blur', onBlur);
    document.removeEventListener('visibilitychange', onVis);
    if (blurred) {
      launchHint.value =
        '已尝试唤起。若仍弹出 Vault not found：说明本机 Obsidian 里还没有这个库——请先完成步骤②打开上方路径，或在步骤④把库名改成 Obsidian 设置里显示的名称。';
    } else {
      launchHint.value =
        '似乎没有成功唤起。请确认已安装 Obsidian，并先用「打开文件夹作为库」选中上方路径；库名需与步骤④一致。';
    }
  }, 2000);
}

async function saveCustomName() {
  const name = customName.value.trim();
  if (!name) return;
  savingName.value = true;
  try {
    const hint = await updateVaultName(name);
    emit('updated', hint);
    emit('status', `库名已更新为 ${hint.launch_vault_name || hint.vault_name}，可再次唤起`);
    launchHint.value = `已保存。唤起将使用：${hint.launch_vault_name || hint.vault_name}`;
  } catch (e) {
    launchHint.value = e instanceof Error ? e.message : '保存库名失败';
  } finally {
    savingName.value = false;
  }
}

async function useFolderName() {
  const name = props.hint?.folder_name;
  if (!name) return;
  customName.value = name;
  await saveCustomName();
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-[130] flex items-center justify-center bg-black/65 p-4 backdrop-blur-sm"
      @click.self="emit('close')"
    >
      <div class="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl border border-amber-400/25 bg-slate-950 shadow-2xl">
        <header class="flex items-center justify-between border-b border-white/10 px-5 py-3">
          <div>
            <p class="text-[10px] uppercase tracking-[0.25em] text-amber-300/70">Connect Obsidian</p>
            <h3 class="text-base font-semibold text-amber-50">接入本地 Obsidian</h3>
          </div>
          <button type="button" class="rounded-lg px-2 py-1 text-xs text-slate-400 hover:bg-white/5" @click="emit('close')">
            关闭
          </button>
        </header>

        <div class="space-y-4 px-5 py-4 text-sm text-slate-200">
          <p v-if="hint?.tip" class="rounded-xl border border-amber-400/20 bg-amber-500/10 px-3 py-2 text-[11px] leading-5 text-amber-50/90">
            {{ hint.tip }}
          </p>

          <ol class="space-y-3 text-xs leading-5">
            <li class="rounded-xl border border-white/10 bg-white/[0.03] p-3" :class="step >= 1 ? 'ring-1 ring-amber-400/20' : ''">
              <p class="font-semibold text-amber-100">① 复制本机知识库路径</p>
              <code class="mt-2 block break-all rounded-lg bg-black/40 px-2 py-1.5 text-[11px] text-amber-50/90">
                {{ hint?.local_path || '（服务端路径不可用时请导出 zip）' }}
              </code>
              <p class="mt-2 text-slate-400">
                文件夹名（Obsidian 默认库名）：
                <code class="text-amber-100">{{ hint?.folder_name || '—' }}</code>
              </p>
              <div class="mt-2 flex flex-wrap gap-2">
                <button
                  type="button"
                  class="rounded-lg border border-amber-400/35 bg-amber-500/15 px-3 py-1.5 text-[11px] font-semibold text-amber-50 hover:bg-amber-500/25"
                  :disabled="copying"
                  @click="copyPath"
                >
                  {{ copying ? '复制中…' : '复制路径' }}
                </button>
                <button
                  type="button"
                  class="rounded-lg border border-white/15 px-3 py-1.5 text-[11px] text-slate-200 hover:bg-white/5"
                  @click="copyFolderName"
                >
                  复制文件夹名
                </button>
                <button
                  type="button"
                  class="rounded-lg border border-sky-400/30 bg-sky-500/10 px-3 py-1.5 text-[11px] text-sky-100 hover:bg-sky-500/20"
                  @click="onExport"
                >
                  导出 zip（兜底）
                </button>
              </div>
            </li>
            <li class="rounded-xl border border-white/10 bg-white/[0.03] p-3">
              <p class="font-semibold text-amber-100">② 在 Obsidian 中打开该文件夹作为库</p>
              <p class="mt-1 text-slate-400">
                Obsidian → 打开其他库 → 「打开文件夹作为库」→ 粘贴上方路径。
                <strong class="text-amber-100/90">不要跳过这一步</strong>，否则会报 Vault not found。
              </p>
              <button
                type="button"
                class="mt-2 rounded-lg border border-white/15 px-3 py-1.5 text-[11px] text-slate-200 hover:bg-white/5"
                @click="step = 3"
              >
                我已完成这一步
              </button>
              <a
                v-if="hint?.install_url"
                class="ml-2 text-[11px] text-sky-300 underline"
                :href="hint.install_url"
                target="_blank"
                rel="noreferrer"
              >
                下载 Obsidian
              </a>
            </li>
            <li class="rounded-xl border border-white/10 bg-white/[0.03] p-3">
              <p class="font-semibold text-amber-100">③ 唤起 Obsidian</p>
              <p class="mt-1 text-slate-400">
                将使用库名
                <code class="text-amber-100">{{ hint?.launch_vault_name || hint?.folder_name }}</code>
                唤起（不会跳出本站）。
              </p>
              <div class="mt-2 flex flex-wrap gap-2">
                <button
                  type="button"
                  class="rounded-lg border px-2 py-1 text-[10px]"
                  :class="launchMode === 'vault' ? 'border-[rgb(var(--lz-accent)/0.5)] bg-[rgb(var(--lz-accent)/0.2)] text-white' : 'border-white/15 text-slate-400'"
                  @click="launchMode = 'vault'"
                >
                  按库名
                </button>
                <button
                  type="button"
                  class="rounded-lg border px-2 py-1 text-[10px]"
                  :class="launchMode === 'path' ? 'border-[rgb(var(--lz-accent)/0.5)] bg-[rgb(var(--lz-accent)/0.2)] text-white' : 'border-white/15 text-slate-400'"
                  @click="launchMode = 'path'"
                >
                  按路径
                </button>
              </div>
              <button
                type="button"
                class="lz-btn lz-btn--primary lz-btn--sm mt-2"
                @click="launchObsidian"
              >
                已完成，唤起 Obsidian
              </button>
              <p v-if="launchHint" class="mt-2 text-[11px] leading-4 text-slate-400">{{ launchHint }}</p>
            </li>
            <li class="rounded-xl border border-white/10 bg-white/[0.03] p-3">
              <p class="font-semibold text-amber-100">④ 仍报 Vault not found？对齐库名</p>
              <p class="mt-1 text-slate-400">
                打开 Obsidian → 设置 → 关于，查看当前库名，填到下方并保存。本机直连可一键使用文件夹名。
              </p>
              <div class="mt-2 flex flex-wrap gap-2">
                <input
                  v-model="customName"
                  type="text"
                  class="min-w-0 flex-1 rounded-lg border border-white/10 bg-black/40 px-2 py-1.5 text-[11px] text-slate-100 outline-none"
                  placeholder="本机 Obsidian 库名"
                />
                <button
                  type="button"
                  class="shrink-0 rounded-lg border border-emerald-400/35 bg-emerald-500/15 px-3 py-1.5 text-[11px] text-emerald-50 hover:bg-emerald-500/25 disabled:opacity-50"
                  :disabled="savingName || !customName.trim()"
                  @click="saveCustomName"
                >
                  {{ savingName ? '保存中…' : '保存库名' }}
                </button>
              </div>
              <button
                v-if="hint?.folder_name"
                type="button"
                class="mt-2 rounded-lg border border-amber-400/30 bg-amber-500/10 px-3 py-1.5 text-[11px] text-amber-50 hover:bg-amber-500/20"
                :disabled="savingName"
                @click="useFolderName"
              >
                使用文件夹名「{{ hint.folder_name }}」
              </button>
            </li>
          </ol>
        </div>
      </div>
    </div>
  </Teleport>
</template>
