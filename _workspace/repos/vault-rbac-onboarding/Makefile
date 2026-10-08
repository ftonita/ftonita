up:
	docker compose up -d
apply:
	VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN=dev-root-token terraform init && \
	VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN=dev-root-token terraform apply -var-file=example.tfvars -auto-approve
test:
	./scripts/smoke-test.sh
down:
	docker compose down -v
