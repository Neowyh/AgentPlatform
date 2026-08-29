install:
	pnpm install

build:
	pnpm build

dev:
	pnpm dev

test:
	bash ../scripts/run-test-lane.sh frontend-standard

test-full:
	bash ../scripts/run-test-lane.sh frontend-core

test-e2e:
	pnpm test:e2e

lint:
	pnpm lint

format:
	pnpm format:write

test-visual:
	pnpm test:e2e:visual

test-visual-update:
	pnpm test:e2e:visual -- --update-snapshots

test-a11y:
	pnpm test:e2e:a11y

test-coverage:
	pnpm vitest run --coverage

build-static:
	NEXT_CONFIG_BUILD_OUTPUT=standalone SKIP_ENV_VALIDATION=1 NEXT_PUBLIC_STATIC_WEBSITE_ONLY=true pnpm build
	@if [ -d .next/static ]; then mkdir -p .next/standalone/.next && cp -R .next/static .next/standalone/.next/static; fi

# 架构边界检查
arch-check:
	npx depcruise src/ --config .dependency-cruiser.cjs

# 生成依赖图（可视化）
arch-graph:
	npx depcruise src/ --config .dependency-cruiser.cjs --output-type dot | dot -T svg > dependency-graph.svg
	@echo "依赖图已生成: dependency-graph.svg"

# Lighthouse CI 性能测试
lighthouse:
	pnpm lhci autorun

# 仅收集报告（不 assert）
lighthouse-collect:
	pnpm lhci collect
