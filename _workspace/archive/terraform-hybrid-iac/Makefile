ENV ?= dev

fmt:
	terraform fmt -recursive

validate:
	@for e in dev stage prod; do \
	  (cd environments/$$e && terraform init -backend=false -input=false >/dev/null && terraform validate) || exit 1; \
	done

plan:
	cd environments/$(ENV) && terraform init -backend-config="bucket=$$TF_STATE_BUCKET" && terraform plan
