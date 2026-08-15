<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { LzBadge, LzButton, LzInput, LzTextarea } from '../../learning/ui';
import { parseApiError } from '../../../api/errors';
import {
  downloadResumeExport,
  fetchCareerTemplates,
  fetchInterviewRoles,
  fetchResumeHtml,
  matchInterviewResume,
  optimizeInterviewResume,
  uploadInterviewResume,
  type InterviewJobRole,
  type ResumeMatchResult,
  type ResumeOpenSourceLink,
  type ResumeOptimizeResult,
  type ResumeTemplateMeta,
} from '../../../api/interview';

const emit = defineEmits<{
  (e: 'open-cabin', payload: { job_role: string }): void;
}>();

const templates = ref<ResumeTemplateMeta[]>([]);
const openSource = ref<ResumeOpenSourceLink[]>([]);
const roles = ref<InterviewJobRole[]>([]);
const templateId = ref('editorial');
const targetRole = ref('backend');
const jd = ref('');
const uploading = ref(false);
const coaching = ref(false);
const matching = ref(false);
const downloading = ref('');
const error = ref('');
const profile = ref<Record<string, unknown>>({});
const preview = ref('');
const optimize = ref<ResumeOptimizeResult | null>(null);
const match = ref<ResumeMatchResult | null>(null);
const photoDataUrl = ref('');

const fields = ref({
  name: '',
  intent: '',
  city: '',
  contact: '',
  email: '',
  github: '',
  education: '',
  skills: '',
  projects: '',
  experience: '',
  certificates: '',
  papers: '',
});

const currentTemplate = computed(
  () => templates.value.find((t) => t.id === templateId.value) || templates.value[0],
);
const allowPhoto = computed(() => currentTemplate.value?.allow_photo !== false);
const lines = (text: string) =>
  text
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean);

const skillChips = computed(() => lines(fields.value.skills));
const contactLine = computed(() =>
  [fields.value.city, fields.value.contact, fields.value.email, fields.value.github].filter(Boolean).join(' · '),
);

onMounted(async () => {
  try {
    const [tpl, roleList] = await Promise.all([fetchCareerTemplates(), fetchInterviewRoles('job')]);
    templates.value = tpl.templates;
    openSource.value = tpl.open_source || [];
    roles.value = roleList;
    if (roleList[0]) targetRole.value = roleList[0].key;
  } catch (err) {
    error.value = parseApiError(err, '模板加载失败');
  }
});

function compressPhoto(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      const canvas = document.createElement('canvas');
      const max = 420;
      let w = img.width;
      let h = img.height;
      if (w > max || h > max) {
        const ratio = Math.min(max / w, max / h);
        w = Math.round(w * ratio);
        h = Math.round(h * ratio);
      }
      canvas.width = w;
      canvas.height = h;
      canvas.getContext('2d')?.drawImage(img, 0, 0, w, h);
      URL.revokeObjectURL(url);
      resolve(canvas.toDataURL('image/jpeg', 0.86));
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error('图片无法读取'));
    };
    img.src = url;
  });
}

async function onPickPhoto(ev: Event) {
  const file = (ev.target as HTMLInputElement).files?.[0];
  if (!file) return;
  error.value = '';
  try {
    photoDataUrl.value = await compressPhoto(file);
  } catch (err) {
    error.value = parseApiError(err, '证件照读取失败');
  }
}

async function onPick(ev: Event) {
  const file = (ev.target as HTMLInputElement).files?.[0];
  if (!file) return;
  uploading.value = true;
  error.value = '';
  try {
    const result = await uploadInterviewResume(file);
    profile.value = result.profile || {};
    preview.value = result.text_preview || '';
    const p = result.profile || {};
    fields.value.name = String(p.name || fields.value.name);
    fields.value.skills = ((p.skills as string[]) || []).join('\n');
    fields.value.education = ((p.education as string[]) || []).join('\n');
    const projects = (p.projects as Array<Record<string, string>>) || [];
    fields.value.projects = projects
      .map((item) => [item.name, item.role, item.highlight].filter(Boolean).join(' / '))
      .join('\n');
    const exp = (p.experience as Array<Record<string, string>>) || [];
    fields.value.experience = exp
      .map((item) => [item.org, item.role, item.highlight].filter(Boolean).join(' / '))
      .join('\n');
  } catch (err) {
    error.value = parseApiError(err, '简历解析失败');
  } finally {
    uploading.value = false;
  }
}

function payload() {
  return {
    text: preview.value,
    profile: profile.value,
    target_role: targetRole.value,
    jd: jd.value,
  };
}

function exportFields() {
  return {
    ...fields.value,
    education: lines(fields.value.education),
    skills: lines(fields.value.skills),
    projects: lines(fields.value.projects),
    experience: lines(fields.value.experience),
    certificates: lines(fields.value.certificates),
    papers: lines(fields.value.papers),
    photo_data_url: allowPhoto.value ? photoDataUrl.value : '',
  };
}

async function runOptimize() {
  coaching.value = true;
  error.value = '';
  try {
    optimize.value = await optimizeInterviewResume(payload());
  } catch (err) {
    error.value = parseApiError(err, '优化失败');
  } finally {
    coaching.value = false;
  }
}

function applyOptimize() {
  if (!optimize.value?.rewritten_markdown) return;
  const text = optimize.value.rewritten_markdown
    .replace(/^#+\s.*/gm, '')
    .replace(/^[-*]\s+/gm, '')
    .trim();
  fields.value.projects = [fields.value.projects, text].filter(Boolean).join('\n');
}

async function runMatch() {
  matching.value = true;
  error.value = '';
  try {
    match.value = await matchInterviewResume(payload());
  } catch (err) {
    error.value = parseApiError(err, '匹配失败');
  } finally {
    matching.value = false;
  }
}

async function doExport(format: 'html' | 'docx' | 'md') {
  downloading.value = format;
  error.value = '';
  try {
    await downloadResumeExport({ template_id: templateId.value, fields: exportFields(), format });
  } catch (err) {
    error.value = parseApiError(err, '导出失败');
  } finally {
    downloading.value = '';
  }
}

async function printPreview() {
  error.value = '';
  try {
    const htmlDoc = await fetchResumeHtml({ template_id: templateId.value, fields: exportFields() });
    const win = window.open('', '_blank', 'noopener,noreferrer,width=900,height=1200');
    if (!win) {
      error.value = '浏览器拦截了打印窗口，请允许弹窗后重试';
      return;
    }
    win.document.write(htmlDoc);
    win.document.close();
    win.focus();
    win.onload = () => win.print();
    setTimeout(() => win.print(), 400);
  } catch (err) {
    error.value = parseApiError(err, '打印失败');
  }
}
</script>

<template>
  <div class="space-y-4">
    <p class="text-xs text-slate-400">
      国内校招习惯右上角证件照；大厂网申请改用「网申安全稿」（不放照片）。请使用近期正装浅底证件照。
    </p>
    <p v-if="error" class="text-xs text-rose-300">{{ error }}</p>

    <div class="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
      <button
        v-for="tpl in templates"
        :key="tpl.id"
        type="button"
        class="resume-pick"
        :class="templateId === tpl.id ? 'is-on' : ''"
        @click="templateId = tpl.id"
      >
        <span class="resume-pick__bar" :style="{ background: tpl.accent }" />
        <p class="text-sm text-slate-100">{{ tpl.name }}</p>
        <p class="mt-1 text-[11px] leading-relaxed text-slate-500">{{ tpl.description }}</p>
        <LzBadge class="mt-2" :tone="tpl.allow_photo === false ? 'neutral' : 'warning'">{{ tpl.suitable }}</LzBadge>
      </button>
    </div>

    <div class="grid gap-4 xl:grid-cols-[minmax(0,22rem)_1fr]">
      <div class="lz-card space-y-3 p-4">
        <label class="block text-xs text-slate-400">
          上传已有简历解析（可选）
          <input class="mt-1 block w-full text-xs" type="file" accept=".pdf,.docx,.txt" @change="onPick" />
        </label>
        <label v-if="allowPhoto" class="block text-xs text-slate-400">
          证件照
          <input class="mt-1 block w-full text-xs" type="file" accept="image/jpeg,image/png,image/webp" @change="onPickPhoto" />
        </label>
        <p v-else class="text-[11px] text-amber-200/80">当前模板为网申安全稿，导出不含照片。</p>
        <p v-if="uploading" class="text-[11px] text-amber-200">解析中…</p>
        <div class="grid gap-2 sm:grid-cols-2">
          <LzInput v-model="fields.name" placeholder="姓名" />
          <LzInput v-model="fields.intent" placeholder="求职意向，如后端开发" />
          <LzInput v-model="fields.city" placeholder="城市" />
          <LzInput v-model="fields.contact" placeholder="电话" />
          <LzInput v-model="fields.email" placeholder="邮箱" />
          <LzInput v-model="fields.github" placeholder="GitHub / 主页" />
          <select v-model="targetRole" class="lz-input h-[34px] text-xs sm:col-span-2">
            <option v-for="role in roles" :key="role.key" :value="role.key">优化对照岗位：{{ role.label }}</option>
          </select>
        </div>
        <LzTextarea v-model="fields.education" :rows="2" placeholder="教育：学校 / 专业 / 时间 / GPA" />
        <LzTextarea v-model="fields.experience" :rows="3" placeholder="实习：公司 / 岗位 / 量化结果" />
        <LzTextarea v-model="fields.projects" :rows="3" placeholder="项目：STAR 量化条目，一行一条" />
        <LzTextarea v-if="templateId === 'folio'" v-model="fields.papers" :rows="2" placeholder="论文 / 竞赛" />
        <LzTextarea v-model="fields.skills" :rows="2" placeholder="技能，一行一条" />
        <LzTextarea v-model="fields.certificates" :rows="2" placeholder="证书：CET-6 / 专业证书" />
        <LzTextarea v-model="jd" :rows="2" placeholder="粘贴目标 JD（可选）" />
        <div class="flex flex-wrap gap-2">
          <LzButton variant="primary" size="sm" :loading="coaching" @click="runOptimize">优化简历</LzButton>
          <LzButton size="sm" :loading="matching" @click="runMatch">岗位匹配</LzButton>
          <LzButton size="sm" @click="printPreview">打印 PDF</LzButton>
          <LzButton size="sm" :loading="downloading === 'html'" @click="doExport('html')">下载 HTML</LzButton>
          <LzButton size="sm" :loading="downloading === 'docx'" @click="doExport('docx')">下载 Word</LzButton>
          <LzButton size="sm" :loading="downloading === 'md'" @click="doExport('md')">下载 Markdown</LzButton>
        </div>
      </div>

      <div class="cv-stage">
        <!-- 金标 / 学术 -->
        <article
          v-if="templateId === 'editorial' || templateId === 'folio'"
          class="cv-sheet"
          :class="templateId === 'folio' ? 'cv-sheet--folio' : 'cv-sheet--editorial'"
        >
          <header class="cv-hero">
            <div>
              <h1>{{ fields.name || '姓名' }}</h1>
              <p class="cv-intent">{{ fields.intent || '求职意向' }}</p>
              <p class="cv-meta">{{ contactLine || '电话 · 邮箱 · 城市' }}</p>
            </div>
            <div class="cv-photo">
              <img v-if="photoDataUrl" :src="photoDataUrl" alt="证件照" />
              <span v-else>证件照</span>
            </div>
          </header>
          <div class="cv-grid">
            <aside>
              <h2>技能</h2>
              <div class="cv-chips">
                <span v-for="s in skillChips" :key="s">{{ s }}</span>
                <span v-if="!skillChips.length" class="cv-muted">待填写</span>
              </div>
              <h2>证书</h2>
              <ul>
                <li v-for="row in lines(fields.certificates)" :key="row">{{ row }}</li>
                <li v-if="!lines(fields.certificates).length" class="cv-muted">CET / 证书</li>
              </ul>
            </aside>
            <main>
              <h2>教育</h2>
              <ul>
                <li v-for="row in lines(fields.education)" :key="row">{{ row }}</li>
                <li v-if="!lines(fields.education).length" class="cv-muted">学校 / 专业 / GPA</li>
              </ul>
              <template v-if="templateId === 'folio'">
                <h2>科研 / 论文</h2>
                <ul>
                  <li v-for="row in lines(fields.papers)" :key="row">{{ row }}</li>
                  <li v-if="!lines(fields.papers).length" class="cv-muted">论文或竞赛</li>
                </ul>
              </template>
              <h2>{{ templateId === 'folio' ? '项目' : '实习经历' }}</h2>
              <ul>
                <li v-for="row in lines(templateId === 'folio' ? fields.projects : fields.experience)" :key="row">{{ row }}</li>
              </ul>
              <h2>{{ templateId === 'folio' ? '实习' : '项目经历' }}</h2>
              <ul>
                <li v-for="row in lines(templateId === 'folio' ? fields.experience : fields.projects)" :key="row">{{ row }}</li>
              </ul>
            </main>
          </div>
        </article>

        <!-- 藏青侧栏 -->
        <article v-else-if="templateId === 'navy_rail'" class="cv-sheet cv-sheet--navy">
          <aside class="cv-rail">
            <div class="cv-photo cv-photo--lg">
              <img v-if="photoDataUrl" :src="photoDataUrl" alt="证件照" />
              <span v-else>证件照</span>
            </div>
            <h1>{{ fields.name || '姓名' }}</h1>
            <p class="cv-intent">{{ fields.intent || '求职意向' }}</p>
            <p class="cv-meta">{{ contactLine || '电话 · 邮箱' }}</p>
            <h2>技能</h2>
            <div class="cv-chips">
              <span v-for="s in skillChips" :key="s">{{ s }}</span>
            </div>
            <h2>证书</h2>
            <ul>
              <li v-for="row in lines(fields.certificates)" :key="row">{{ row }}</li>
            </ul>
          </aside>
          <div class="cv-main">
            <h2>教育</h2>
            <ul>
              <li v-for="row in lines(fields.education)" :key="row">{{ row }}</li>
            </ul>
            <h2>实习经历</h2>
            <ul>
              <li v-for="row in lines(fields.experience)" :key="row">{{ row }}</li>
            </ul>
            <h2>项目经历</h2>
            <ul>
              <li v-for="row in lines(fields.projects)" :key="row">{{ row }}</li>
            </ul>
          </div>
        </article>

        <!-- ATS -->
        <article v-else class="cv-sheet cv-sheet--ats">
          <h1>{{ fields.name || 'Name' }}</h1>
          <p class="cv-intent">{{ fields.intent || 'Target role' }}</p>
          <p class="cv-meta">{{ contactLine || 'Phone · Email' }}</p>
          <h2>Education</h2>
          <ul>
            <li v-for="row in lines(fields.education)" :key="row">{{ row }}</li>
          </ul>
          <h2>Experience</h2>
          <ul>
            <li v-for="row in lines(fields.experience)" :key="row">{{ row }}</li>
          </ul>
          <h2>Projects</h2>
          <ul>
            <li v-for="row in lines(fields.projects)" :key="row">{{ row }}</li>
          </ul>
          <h2>Skills</h2>
          <p>{{ skillChips.join(' · ') || '—' }}</p>
        </article>
      </div>
    </div>

    <div v-if="optimize" class="lz-card space-y-2 p-4">
      <div class="flex flex-wrap items-center gap-2">
        <p class="text-sm text-amber-100">优化评分 {{ optimize.score }}</p>
        <LzBadge v-if="optimize.degraded" tone="warning">降级</LzBadge>
        <LzButton size="sm" variant="primary" @click="applyOptimize">填入模板</LzButton>
      </div>
      <ul class="space-y-1 text-xs text-slate-400">
        <li v-for="issue in optimize.issues" :key="issue">· {{ issue }}</li>
      </ul>
      <pre class="whitespace-pre-wrap text-xs text-slate-200">{{ optimize.rewritten_markdown }}</pre>
    </div>

    <div v-if="match" class="lz-card space-y-2 p-4">
      <p class="text-sm text-amber-100">匹配分 {{ match.score }}</p>
      <p class="text-xs text-emerald-300">已覆盖：{{ match.matched.join('、') || '—' }}</p>
      <p class="text-xs text-rose-300">缺口：{{ match.gaps.join('、') || '—' }}</p>
      <LzButton size="sm" variant="primary" @click="emit('open-cabin', { job_role: targetRole })">用该岗位开面试舱</LzButton>
    </div>

    <p v-if="openSource.length" class="text-[10px] text-slate-600">
      排版参考（非使用入口）：
      <a
        v-for="os in openSource"
        :key="os.id"
        class="ml-1 text-slate-500 underline"
        :href="os.url"
        target="_blank"
        rel="noopener noreferrer"
      >{{ os.name }}</a>
    </p>
  </div>
</template>

<style scoped>
.resume-pick {
  text-align: left;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(15, 23, 42, 0.55);
  padding: 12px;
}
.resume-pick.is-on {
  border-color: rgba(245, 158, 11, 0.55);
  box-shadow: 0 0 0 1px rgba(245, 158, 11, 0.25);
}
.resume-pick__bar {
  display: block;
  height: 4px;
  border-radius: 999px;
  margin-bottom: 10px;
}
.cv-stage {
  overflow: auto;
  border-radius: 16px;
  background:
    radial-gradient(ellipse at 20% 0%, rgba(245, 158, 11, 0.12), transparent 40%),
    #0b0b10;
  padding: 16px;
}
.cv-sheet {
  min-height: 520px;
  background: #fff;
  color: #1c1917;
  border-radius: 4px;
  padding: 22px 24px;
}
.cv-sheet h1 {
  margin: 0;
  font-size: 26px;
  letter-spacing: 0.04em;
}
.cv-sheet h2 {
  margin: 14px 0 6px;
  font-size: 11px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
}
.cv-sheet ul {
  margin: 0;
  padding-left: 16px;
  font-size: 12.5px;
  line-height: 1.55;
}
.cv-intent {
  margin: 4px 0 0;
  font-size: 13px;
  font-weight: 600;
}
.cv-meta {
  margin: 6px 0 0;
  font-size: 11.5px;
  color: #57534e;
}
.cv-muted {
  color: #a8a29e;
  list-style: none;
  margin-left: -16px;
}
.cv-hero {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}
.cv-photo {
  width: 86px;
  height: 112px;
  flex-shrink: 0;
  overflow: hidden;
  border: 1px solid #d6d3d1;
  background: #f5f5f4;
  color: #a8a29e;
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.cv-photo img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.cv-photo--lg {
  width: 108px;
  height: 140px;
  margin: 0 auto 10px;
  border-color: #fbbf24;
}
.cv-grid {
  display: grid;
  grid-template-columns: 32% 1fr;
  gap: 18px;
  margin-top: 14px;
}
.cv-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.cv-chips span {
  border: 1px solid #e7d3a1;
  color: #92400e;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 11px;
}
.cv-sheet--editorial {
  border-top: 3px solid #b8860b;
}
.cv-sheet--editorial h2 {
  color: #b8860b;
  border-bottom: 1px solid #f0e6c8;
  padding-bottom: 3px;
}
.cv-sheet--folio h1,
.cv-sheet--folio h2 {
  font-family: 'Songti SC', 'SimSun', serif;
}
.cv-sheet--folio h2 {
  color: #4c1d95;
}
.cv-sheet--navy {
  display: grid;
  grid-template-columns: 200px 1fr;
  padding: 0;
  min-height: 560px;
}
.cv-rail {
  background: #1e3a5f;
  color: #e8eef6;
  padding: 22px 16px;
}
.cv-rail h1 {
  font-size: 22px;
  color: #fff;
  margin-top: 8px;
}
.cv-rail h2 {
  color: #fbbf24;
}
.cv-rail .cv-intent,
.cv-rail .cv-meta {
  color: #cbd5e1;
}
.cv-rail .cv-chips span {
  color: #e2e8f0;
  border-color: #64748b;
}
.cv-main {
  padding: 22px 20px;
}
.cv-main h2 {
  color: #1e3a5f;
  border-left: 3px solid #b8860b;
  padding-left: 8px;
  letter-spacing: 0.12em;
}
.cv-sheet--ats h2 {
  color: #0f172a;
  letter-spacing: 0;
  text-transform: none;
  border-bottom: 1px solid #cbd5e1;
}
</style>
