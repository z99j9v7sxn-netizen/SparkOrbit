<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { codelabExercise, codelabExplain, codelabHint, codelabPassed, codelabRun } from '../../api/challengeSprint';
import { useOrbitStore } from '../../stores/orbit';
import { LzButton, LzSkeleton, LzTextarea } from './ui';

type CodelabTest = { stdin?: string; expected_stdout?: string };

const orbit = useOrbitStore();
const planetSlug = computed(() => orbit.selectedPlanet?.slug || '');
const loading = ref(false);
const code = ref('print("hello")\n');
const output = ref('');
const hint = ref('');
const explain = ref('');
const title = ref('');
const prompt = ref('');
const status = ref('');
const serverRunning = ref(false);
const testing = ref(false);
const tests = ref<CodelabTest[]>([]);
const testReport = ref('');
let pyodide: any = null;

async function ensurePyodide() {
  if (pyodide) return pyodide;
  if (!(window as any).loadPyodide) {
    await new Promise<void>((resolve, reject) => {
      const s = document.createElement('script');
      s.src = 'https://cdn.jsdelivr.net/pyodide/v0.26.4/full/pyodide.js';
      s.onload = () => resolve();
      s.onerror = () => reject(new Error('Pyodide 加载失败'));
      document.head.appendChild(s);
    });
  }
  pyodide = await (window as any).loadPyodide({ indexURL: 'https://cdn.jsdelivr.net/pyodide/v0.26.4/full/' });
  return pyodide;
}

function normalizeOut(s: string) {
  return String(s || '')
    .replace(/\r\n/g, '\n')
    .trimEnd();
}

async function loadExercise() {
  if (!planetSlug.value) return;
  loading.value = true;
  status.value = '';
  testReport.value = '';
  explain.value = '';
  try {
    const ex = (await codelabExercise(planetSlug.value)) as {
      title?: string;
      prompt?: string;
      starter_code?: string;
      tests?: CodelabTest[];
    };
    title.value = ex.title || '微习题';
    prompt.value = ex.prompt || '';
    code.value = ex.starter_code || code.value;
    tests.value = Array.isArray(ex.tests) ? ex.tests : [];
  } catch (e) {
    status.value = String(e);
  } finally {
    loading.value = false;
  }
}

async function runCode() {
  output.value = '运行中…';
  try {
    const py = await ensurePyodide();
    await py.runPythonAsync(`
import sys
from io import StringIO
sys.stdout = StringIO()
`);
    await py.runPythonAsync(code.value);
    const out = await py.runPythonAsync('sys.stdout.getvalue()');
    output.value = String(out || '(无输出)');
  } catch (e: any) {
    output.value = String(e?.message || e);
  }
}

async function runOnServer() {
  serverRunning.value = true;
  output.value = '服务端运行中…';
  try {
    const res = await codelabRun(code.value, 3);
    const parts = [res.stdout, res.stderr].filter(Boolean);
    output.value = parts.join('\n') || '(无输出)';
    if (res.runner) {
      status.value = `执行完成（${res.runner}，exit=${res.exit_code}）`;
    }
  } catch (e: any) {
    output.value = String(e?.message || e);
  } finally {
    serverRunning.value = false;
  }
}

async function askHint() {
  if (!planetSlug.value) return;
  const res = await codelabHint(planetSlug.value, code.value, prompt.value);
  hint.value = `${res.hint || ''}\n${res.next_question || ''}`;
}

async function askExplain() {
  if (!planetSlug.value) return;
  const res = await codelabExplain(planetSlug.value, code.value, prompt.value);
  explain.value = [res.explain, res.pitfalls ? `常见坑：${res.pitfalls}` : '', res.next_step ? `下一步：${res.next_step}` : '']
    .filter(Boolean)
    .join('\n');
}

async function runOneTest(py: any, t: CodelabTest): Promise<{ ok: boolean; got: string; expected: string }> {
  const expected = normalizeOut(t.expected_stdout || '');
  await py.runPythonAsync(`
import sys
from io import StringIO
sys.stdout = StringIO()
`);
  // 多数微习题不读 stdin；若有 stdin 注入 sys.stdin
  if (t.stdin) {
    const escaped = JSON.stringify(String(t.stdin));
    await py.runPythonAsync(`
import sys
from io import StringIO
sys.stdin = StringIO(${escaped})
`);
  }
  await py.runPythonAsync(code.value);
  const got = normalizeOut(String(await py.runPythonAsync('sys.stdout.getvalue()') || ''));
  return { ok: got === expected, got, expected };
}

async function runTestsAndPass() {
  if (!planetSlug.value) return;
  testing.value = true;
  status.value = '';
  testReport.value = '';
  try {
    const suite = tests.value.length ? tests.value : [{ stdin: '', expected_stdout: '' }];
    if (!tests.value.length) {
      status.value = '本题无测例，请先「重新出题」或手动核对输出后再记用闸。';
      return;
    }
    const py = await ensurePyodide();
    let passed = 0;
    const lines: string[] = [];
    for (let i = 0; i < suite.length; i += 1) {
      try {
        const r = await runOneTest(py, suite[i]);
        if (r.ok) {
          passed += 1;
          lines.push(`#${i + 1} ✓`);
        } else {
          lines.push(`#${i + 1} ✗ 期望「${r.expected}」实际「${r.got}」`);
        }
      } catch (e: any) {
        lines.push(`#${i + 1} ✗ 运行错误：${e?.message || e}`);
      }
    }
    testReport.value = lines.join('\n');
    output.value = testReport.value;
    if (passed < suite.length) {
      status.value = `测例 ${passed}/${suite.length} 未全绿，无法过用闸`;
      return;
    }
    const res = await codelabPassed(planetSlug.value, passed, suite.length);
    status.value = res.lit ? `测例全绿 ${passed}/${suite.length} · 用闸通过，行星已点亮！` : `测例全绿 ${passed}/${suite.length} · 用闸已记录`;
    try {
      const { clipNote } = await import('../../api/challengeSprint');
      await clipNote(planetSlug.value, {
        kind: 'code_clip',
        title: title.value || '代码舱测例',
        text: `测例 ${passed}/${suite.length} 全绿\n${prompt.value.slice(0, 200)}`,
        planet_slug: planetSlug.value,
      }, `代码舱 · ${title.value || planetSlug.value}`);
    } catch {
      /* 剪藏失败不挡过闸 */
    }
  } catch (e: any) {
    status.value = String(e?.message || e);
  } finally {
    testing.value = false;
  }
}

onMounted(() => void loadExercise());
watch(planetSlug, () => void loadExercise());
</script>

<template>
  <div class="space-y-3 text-slate-200">
    <div class="flex items-start justify-between gap-2">
      <div class="min-w-0">
        <p class="lz-caption lz-accent-text uppercase tracking-[0.3em] opacity-80">Code Lab</p>
        <h3 class="lz-title mt-0.5">代码实操舱</h3>
        <p class="lz-caption mt-0.5">
          {{ title || '选择行星后出题' }} · 测例全绿才记用闸
          <span v-if="tests.length" class="lz-accent-text">（{{ tests.length }} 组测例）</span>
        </p>
      </div>
      <LzButton variant="ghost" size="sm" :disabled="loading" @click="loadExercise">重新出题</LzButton>
    </div>
    <LzSkeleton v-if="loading" preset="text" :rows="2" />
    <p v-else class="lz-body">{{ prompt }}</p>
    <LzTextarea v-model="code" :rows="12" class="font-mono" />
    <div class="flex flex-wrap items-center gap-2">
      <LzButton variant="soft" size="sm" @click="runCode">运行</LzButton>
      <LzButton variant="ghost" size="sm" :disabled="serverRunning" @click="runOnServer">
        {{ serverRunning ? '服务端…' : '服务端运行' }}
      </LzButton>
      <LzButton variant="ghost" size="sm" @click="askHint">AI 提示</LzButton>
      <LzButton variant="ghost" size="sm" @click="askExplain">AI 讲解</LzButton>
      <LzButton variant="primary" size="sm" :disabled="testing || !tests.length" @click="runTestsAndPass">
        {{ testing ? '跑测例…' : '跑测例 · 过用闸' }}
      </LzButton>
    </div>
    <pre class="lz-card lz-card--flat max-h-40 overflow-auto p-3 font-mono text-[11px] text-slate-300">{{ output || '输出区' }}</pre>
    <p v-if="hint" class="lz-card lz-card--flat lz-desc whitespace-pre-wrap p-2.5">{{ hint }}</p>
    <p
      v-if="explain"
      class="whitespace-pre-wrap rounded-[var(--radius-ctl)] border border-[rgb(var(--lz-accent)/0.2)] bg-[rgb(var(--lz-accent)/0.05)] p-2.5 text-xs text-slate-200"
    >
      {{ explain }}
    </p>
    <p v-if="status" class="text-xs text-emerald-300">{{ status }}</p>
  </div>
</template>
