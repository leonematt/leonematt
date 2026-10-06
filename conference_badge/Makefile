PY ?= python3

.PHONY: uf2 flash screens check-portfolio clean

uf2:            ## build build/tufty-badge.uf2 from drive/
	$(PY) build_uf2.py

flash:          ## build, then copy onto the badge (hold BOOT, tap RESET first)
	$(PY) build_uf2.py --flash

screens:        ## regenerate the Conf Badge name card + QR from tools/make_screens.py
	$(PY) tools/make_screens.py -o drive/apps/conf_badge/assets

check-portfolio: ## run the Fractal Securities app's parser against the live site
	$(PY) tools/check_portfolio.py

clean:
	rm -rf build
