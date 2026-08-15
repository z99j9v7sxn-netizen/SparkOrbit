import { defineStore } from 'pinia';
import { computed, ref } from 'vue';
import { fetchTeacherClasses, type TeacherClass } from '../api/teacher';

const STORAGE_KEY = 'sparkorbit_teacher_class_id';

export const useTeacherClassStore = defineStore('teacherClass', () => {
  const classes = ref<TeacherClass[]>([]);
  const classId = ref('');
  const loading = ref(false);
  const error = ref('');

  const currentClass = computed(() => classes.value.find((c) => c.id === classId.value) ?? null);
  const currentClassName = computed(() => currentClass.value?.name ?? '');
  const inviteCode = computed(() => currentClass.value?.invite_code ?? '');
  const hasClasses = computed(() => classes.value.length > 0);

  async function loadClasses() {
    loading.value = true;
    error.value = '';
    try {
      classes.value = await fetchTeacherClasses();
      const saved = localStorage.getItem(STORAGE_KEY) ?? '';
      if (saved && classes.value.some((c) => c.id === saved)) {
        classId.value = saved;
      } else {
        classId.value = classes.value[0]?.id ?? '';
      }
      if (classId.value) localStorage.setItem(STORAGE_KEY, classId.value);
    } catch (err) {
      error.value = err instanceof Error ? err.message : '加载班级失败';
      classes.value = [];
      classId.value = '';
    } finally {
      loading.value = false;
    }
  }

  function setClassId(id: string) {
    classId.value = id;
    if (id) localStorage.setItem(STORAGE_KEY, id);
  }

  return {
    classes,
    classId,
    loading,
    error,
    currentClass,
    currentClassName,
    inviteCode,
    hasClasses,
    loadClasses,
    setClassId,
  };
});
