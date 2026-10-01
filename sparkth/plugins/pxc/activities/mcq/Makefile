build: sandbox.wasm

# npm ci deletes node_modules and reinstalls, so gate it on the lockfile. touch marks the
# directory newer than the lockfile, which npm ci does not guarantee.
node_modules: package-lock.json
	npm ci
	touch node_modules

# Compiled straight from the single-file source, the way the activity builder compiles one.
sandbox.wasm: sandbox.js pxc.wit node_modules
	npx componentize-js sandbox.js --wit pxc.wit --world-name activity --disable http --disable fetch-event -o sandbox.wasm
