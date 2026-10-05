TOOLCHAIN := ../../builder/toolchain

build: sandbox.wasm

# npm ci deletes node_modules and reinstalls, so gate it on the lockfile. touch marks the
# directory newer than the lockfile, which npm ci does not guarantee.
$(TOOLCHAIN)/node_modules: $(TOOLCHAIN)/package-lock.json
	npm ci --prefix $(TOOLCHAIN)
	touch $(TOOLCHAIN)/node_modules

# Compiled with the activity builder's toolchain, the way the builder compiles one.
sandbox.wasm: sandbox.js $(TOOLCHAIN)/compile.mjs $(TOOLCHAIN)/pxc.wit $(TOOLCHAIN)/node_modules
	node $(TOOLCHAIN)/compile.mjs sandbox.js $(TOOLCHAIN)/pxc.wit sandbox.wasm
