# Source from the repository root, with the emulator running: . bin/env.sh
# Clears every AWS_* variable (real credentials, AWS_PROFILE) so the CLI cannot reach real AWS,
# then points it at the emulator using the CA and credentials the emulator generated.
for v in $(env | sed -n 's/^\(AWS_[A-Za-z_]*\)=.*/\1/p'); do unset "$v"; done
_name=${EMULATOR_CONTAINER:-aws-emulator}
_port=${EMULATOR_PORT:-9297}
mkdir -p run
docker cp "$_name:/home/emulator/.aws/emulator/9297/ca.pem" run/ca.pem
docker cp "$_name:/home/emulator/.aws/emulator/9297/emulator_credentials" run/credentials
chmod 600 run/credentials
export AWS_ENDPOINT_URL="https://127.0.0.1:${_port}"
export AWS_CA_BUNDLE="$PWD/run/ca.pem"
export AWS_SHARED_CREDENTIALS_FILE="$PWD/run/credentials"
export AWS_CONFIG_FILE=/dev/null
export AWS_DEFAULT_REGION=us-east-1
unset _name _port
