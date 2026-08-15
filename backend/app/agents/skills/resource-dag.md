---
description: 资源生成 DAG 规则。修改资源编排时加载。
---

组1 并行：doc / mindmap / media / deck / code  
组2：quiz 依赖 doc（若请求了 doc）  
组3：reading 依赖 doc+mindmap（若请求了对应类型）  
每组使用独立 DB session 并行执行，禁止全局大锁串行化整组。
