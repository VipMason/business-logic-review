# Project Startup and Deployment Guide

For a complete project review, write `{topic}启动与部署.md` in `{project-root}/docs/启动部署/`, alongside `docs/业务梳理/`. Use Simplified Chinese. Reuse the frontend inventory, application names, evidence scope, and project version from the business review. For a requested partial scope, document the requested applications and their startup dependencies.

## Evidence

- Inspect package scripts and lockfiles, application entry points, manifests, sample environment files, runtime versions, container and deployment manifests, reverse proxies, pipelines, and existing operator instructions. Confirm what each script actually runs before recording it.
- Follow the deployed chain from user application to API, gateway, database, cache, and relevant external or internal integrations. Record startup order, port and routing where evidenced, and which components can be tested independently.
- Distinguish the intended repository workflow, an environment-specific example, and the actual verified deployment. Identify broken references, missing services in orchestration, unconfirmed artifacts, and optional or legacy configurations.
- Document configuration keys, source locations, purpose, and whether required for startup or a particular feature. Use placeholders for secrets, personal data, and sensitive environment details. Keep project-specific evidence in the target project deliverable.

## Document

1. **端与服务总览** — Show each frontend and supporting service, source directory, local entry and deployment approach. Note the status of H5 targets or embedded pages when applicable.
2. **本地启动** — Give prerequisites, working directories, dependency installation, environment selection, commands, startup order, ports or URLs, and a minimal verification action. Use actual scripts and distinguish source import from generated output directories for mini-programs.
3. **构建与部署** — For each application, show the build command or tool workflow, output directory, target, routing and release prerequisites, and post-deployment checks. For mini-programs, include manifest/AppID location, developer-tool import directory, account and domain configuration, upload, review, and release. Cover relevant backend profiles and database initialization/migrations, with environment or data-changing steps called out.
4. **验证结果与待确认项** — Record the commands actually run, environment, outcome and blockers. Use isolated local or test checks that stay within the user's requested scope. Building artifacts or checking local startup does not authorize changing a real deployment.

Use repository-relative evidence links from the output location. Validate the links, working directories, script names, artifact paths, and agreement with the business review. If only source evidence is available, mark startup or deployment status as unverified with the concrete reason.
