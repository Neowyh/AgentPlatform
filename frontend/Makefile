install:
	pnpm install

build:
	pnpm build

dev:
	pnpm dev

test:
	pnpm test

test-e2e:
	pnpm test:e2e

lint:
	pnpm lint

format:
	pnpm format:write

test-visual:
	npx playwright test tests/e2e/visual/ --project=chromium --reporter=list

test-visual-update:
	npx playwright test tests/e2e/visual/ --project=chromium --update-snapshots

test-a11y:
	npx playwright test tests/e2e/a11y/ --project=chromium --reporter=list

build-static:
	NEXT_CONFIG_BUILD_OUTPUT=standalone SKIP_ENV_VALIDATION=1 NEXT_PUBLIC_STATIC_WEBSITE_ONLY=true pnpm build
	@if [ -d .next/static ]; then mkdir -p .next/standalone/.next && cp -R .next/static .next/standalone/.next/static; fi
