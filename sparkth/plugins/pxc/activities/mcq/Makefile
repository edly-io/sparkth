build: sandbox.wasm

# npm ci deletes node_modules and reinstalls, so gate it on the lockfile. touch marks the
# directory newer than the lockfile, which npm ci does not guarantee.
node_modules: package-lock.json
	npm ci
	touch node_modules

sandbox.bundle.js: sandbox.js node_modules
	npx esbuild sandbox.js --bundle --format=esm --platform=neutral '--external:pxc:sandbox/*' --outfile=sandbox.bundle.js

sandbox.wasm: sandbox.bundle.js pxc.wit
	npx componentize-js sandbox.bundle.js --wit pxc.wit --world-name activity --disable http --disable fetch-event -o sandbox.wasm
