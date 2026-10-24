# 工程数据手动复制规则
只复制旧 ZIP 最外层 `BYOP_Engineering_Data_Package_v1.0_2026-10-23/` 里的 `raw` 和 `processed` 的完整内容到本目录同名两个子文件夹。不要嵌套根目录名。建议同时把原包 `config/engineering_baseline.json`（如果存在且不在 processed 内）及原包 `manifest/` 和 `scripts/validate_package.py` 这些**轻量文件**复制到 `reference/` 并保留其原来的相对路径；原包中其他小文件（如 README、docs、来源说明）若便于复核也可复制到 `reference/`，避免覆盖新包的 docs 和 scripts；这些文件不是取代主仓库的代码。
