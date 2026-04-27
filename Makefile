.PHONY: all stats tools clean

all: stats tools

stats:
	python3 scripts/build_stats.py

tools:
	python3 scripts/build_tools.py

clean:
	rm -f assets/*.svg
	rm -rf assets/icons
