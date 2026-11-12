# radeon-cloud-images

Radeon Cloud 选择器里“稳定行”镜像的唯一来源（owner 决定 D-20261112-26、-27、-28）。**每个镜像都用 Dockerfile 定义，PR 合入 main 就是发布门禁。**

## 结构
```
images/<name>/
  Dockerfile   # 第一行 "# upstream: <registry>/<repo>:<tag>@sha256:..."，FROM 指向无锡 Harbor 里同一个 digest
  image.yaml   # rc_repo（Harbor 别名仓库）、catalog_row（目录稳定行）、smoke 类别、upstream tag 规则
  smoke.sh     # 在镜像里跑，1 张 W7900D；成功最后打印 "SMOKE PASS"
tools/
  release.py         # 一个镜像的完整发布：镜像上游 → 冒烟 → rc-current → 目录（GT → Global → 中国站）
  mirror.sh          # 按 digest 断点续传（无锡出口单连接约 10 分钟会被切断），然后 crane push
  harbor.py catalog.py upstream_check.py
  ci/slot_pool.py    # 和 RCI CI 共用的 GPU 槽位租约（从 RCI 复制，需保持一致）
.github/workflows/
  release.yml        # main 上 images/** 有变化就发布
  upstream-check.yml # 每天检查上游；有新版本由 bot 开升级 PR（不直接改目录）
  rollback.yml       # 手动一键回滚
```

## 发布流程（`release.yml`）
1. **镜像**：Harbor 里还没有上游 digest 时，按 digest 断点续传到 `radeon-cloud-global/<上游 repo>:<tag>`（digest 不变）。节点永远不直连外网拉大镜像。
2. **冒烟**：用 `tools/ci/slot_pool.py` 领一个 CI 槽位，在槽位命名空间起一个 1 卡 Job（节点 `amd-oneclick.io/workload-ci=enabled`），运行 `smoke.sh`。没有 `SMOKE PASS` 就算失败。
3. **上别名**：把 digest 服务端复制到 `radeon-cloud-global/rc/<分类>`，原来的 `rc-current` 改名为 `rc-prev`，`rc-current` 指向新 digest。
4. **上目录**：依次在 GT → Global → 中国站，对 `catalog_row` 那一行调 `POST /api/admin/images/{id}/harbor`（检测 drift）和 `.../harbor/adopt`。**只改稳定行**；adopt 前查 `GET /api/admin/templates`，有模板指向这一行就拒绝。
5. **失败**：不移动别名、不改目录，在当天的“镜像流水线日报”issue 记一条。
6. **生产 +1h**：启动失败率比发布前变差就自动回滚（`watch.yml`，首批上生产前补上）。

## 回滚
Actions → rollback → 填 image 和 sites：`rc-current` 指回 `rc-prev`，再 adopt，约 1 分钟生效。被回退的 digest 留在 `rc-rolled-back`。

## 新增或升级镜像
- **升级**：改 `Dockerfile` 第一行的 tag@digest 和 `FROM` 的 digest（bot 每天自动开这种 PR），看上游 release notes，合入即发布。
- **新增**：新建 `images/<name>/`（三个文件），先让 rc-ux 在 Admin 建好跟踪 `rc/<分类>:rc-current` 的稳定行。带 RUN/COPY 的 Dockerfile 会用 Kaniko 构建（第二批支持；SGLang+hk-dsl 由 hk-B 提 PR）。

## 凭据（都不进 GitHub）
放在 runner 所在命名空间 `amd-oneclick-ci-runners` 的 k8s Secret 里，workflow 运行时读到 `$RUNNER_TEMP`，用完即删，不打印：
- `radeon-images-harbor`（`.dockerconfigjson`）：Harbor robot，只限 `radeon-cloud-global` 项目 push/pull。
- `radeon-images-catalog`（键 `gt`/`global`/`china`）：各站 scoped operator token，只开放 `GET /api/admin/images`、`GET /api/admin/templates`、`POST /api/admin/images/{image_id}/harbor`、`POST /api/admin/images/{image_id}/harbor/adopt`。有效期 90 天，到期前 14 天在日报 issue 提醒轮换。

仓库变量（非机密）：`CATALOG_URL_GT`、`CATALOG_URL_GLOBAL`、`CATALOG_URL_CHINA`（集群内各站 manager 的地址）。

## Runner
集群内一个只服务本仓库的 runner（label `radeon-images`，`amd-oneclick-ci-runners` 命名空间，用 `gh-runner` 服务账号，所以有 CI 槽位租约和槽位命名空间的权限）。注册只用一次性的 registration token，集群里只保存 runner 自己的凭据，不存 PAT。

## 分支保护（main）
需要 1 个 CODEOWNERS 批准；不允许直接推送，管理员也不例外；需要通过 `plan` 检查；禁止强推和删除分支。

## 状态
首批：PyTorch 稳定版、PyTorch 最新版、vLLM。第二批：Base、Unsloth、SGLang+hk-dsl（hk-B）。llama.cpp、ComfyUI 后续再加。
