# Streamlit 导航冲突修复说明

## 现象
启动后左侧额外出现：`app / comparison / data notes / dispatch / hourly view / overview / stress test / validation`。点击这些英文入口时出现空白或报错。

## 根因
Streamlit 把项目根目录下的 `pages/` 视为**保留的原生多页面目录**，自动将其中每个 `.py` 文件注册成独立页面。

但本工程本来的架构是：

- `app.py` 是唯一入口；
- `app.py` 用中文 `st.radio()` 自定义导航；
- 各页面文件只提供 `render()` 函数，供 `app.py` 调用。

因此 `pages/` 的自动发现机制与自定义路由发生冲突。即使 `.streamlit/config.toml` 设置了 `showSidebarNavigation = false`，在不同 Streamlit 版本、启动位置或配置加载环境下也不应依赖它作为唯一防线。

## 本版修复

- `pages/` → `views/`
- `app.py` 改为 `from views import ...`
- 顶层不再保留 `pages/`
- 新增 `navigation_structure_test.py`
- `run_windows.bat` 启动前自动执行导航结构检查

## 正确启动方式
在**工程根目录**运行：

```bash
python -m streamlit run app.py
```

不要单独运行 `views/overview.py`、`views/dispatch.py` 等文件。
