# Tennis DX
#   make          build build/tennis_dx.gbc
#   make test     regression tests (needs: pip install pyboy pillow)
#   make audit    build/audit.gbc: the ROM plus counters of VRAM writes outside VBlank (used by make test)
#   make ips      build/tennis_dx.ips (patch for your own dump)
#   make lint     style check of the Python scripts (needs ruff)
#   make dist     dist/: ROM, IPS patch and source archive
#   make poses    build/poses.png: every pose of both players
#   make clean

BASEROM_SHA1 := ec45a932fb3fc21394fef5e27e7fe9eccd0c7f70
ROM   := build/tennis_dx.gbc
PY    ?= python3

SRC := $(wildcard src/*.asm src/*.inc)

all: $(ROM)

build/baserom.ok: baserom.gb
	@mkdir -p build
	@echo "$(BASEROM_SHA1)  baserom.gb" | sha1sum -c --quiet - \
	  || (echo "baserom.gb is not Tennis (World) - expected SHA1 $(BASEROM_SHA1)"; exit 1)
	@touch $@

# Tile snapshots of the original game, taken from your own baserom.gb
# (they are not stored in the repository).
VRAM := build/vram/spr_court.bin build/vram/spr_board.bin build/vram/bg_court.bin build/vram/bg_board.bin build/vram/map_court.bin

$(VRAM) &: baserom.gb build/baserom.ok tools/dump_vram.py
	$(PY) tools/dump_vram.py baserom.gb build/vram

build/data.inc: tools/gen_data.py tools/palettes.py tools/art/dx_logo.py $(wildcard tools/data/*.json) $(VRAM)
	@mkdir -p build
	$(PY) tools/gen_data.py $@ build/vram

build/main.o: $(SRC) build/data.inc build/baserom.ok
	rgbasm -Wall -I src/ -I build/ -I ./ -o $@ src/main.asm

$(ROM): build/main.o
	rgblink -n build/tennis_dx.sym -m build/tennis_dx.map -p 0xFF -o $@ $<
	rgbfix -c -s -l 0x33 -k 01 -m MBC5 -t "TENNIS" -v -p 0xFF $@
	$(PY) tools/check_rom.py $@ baserom.gb

ips: build/tennis_dx.ips
build/tennis_dx.ips: $(ROM)
	$(PY) tools/make_ips.py baserom.gb $(ROM) $@

test: $(ROM) build/audit.gbc
	$(PY) tests/run_tests.py $(ROM) baserom.gb

lint:
	ruff check --select E,F,W --ignore E501 tools tests

# Everything worth sharing; the original game is never included.
dist: $(ROM) build/tennis_dx.ips
	rm -rf dist && mkdir -p dist
	cp $(ROM) "dist/Tennis DX.gbc"
	cp build/tennis_dx.ips dist/tennis_dx.ips
	zip -qr dist/tennis-dx-src.zip . -x 'build/*' 'dist/*' 'baserom.gb' '*.gb' '*.gbc' '*.png' '*__pycache__/*' '.ruff_cache/*'

# Every pose of both players, as a picture (the game's graphics: stays in build/)
poses: build/poses.png
build/poses.png: $(ROM) tools/poses.py
	$(PY) tools/poses.py $(ROM) $@ 40000 1,2,3,4,5,6

# Same ROM, plus counters of VRAM / palette writes outside VBlank (tests/audit.py)
audit: build/audit.gbc
build/audit.gbc: $(SRC) build/data.inc build/baserom.ok
	rgbasm -Wall -DVRAM_AUDIT -I src/ -I build/ -I ./ -o build/audit.o src/main.asm
	rgblink -n build/audit.sym -o $@ build/audit.o
	rgbfix -c -s -l 0x33 -k 01 -m MBC5 -t "TENNIS" -v -p 0xFF $@

clean:
	rm -rf build dist .ruff_cache tools/__pycache__ tools/art/__pycache__

.PHONY: all ips test lint poses dist audit clean
