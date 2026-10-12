.PHONY: setup test demo lint image migrate serve frontend

setup test demo lint image migrate serve:
	$(MAKE) -C backend $@

frontend:
	cd frontend && npm run dev
