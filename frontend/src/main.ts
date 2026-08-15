import { createApp } from 'vue';
import { createPinia } from 'pinia';
import router from './router';
import App from './App.vue';
import { glow } from './directives/glow';
import './style.css';

createApp(App).use(createPinia()).use(router).directive('glow', glow).mount('#app');
