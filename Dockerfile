# AWS Emulator pinned by version and package checksum. ARM64 only.
# Rebuild fails if the package at the URL no longer matches the checksum.
FROM public.ecr.aws/amazonlinux/amazonlinux:2023-minimal

ARG EMULATOR_VERSION=1.0.338
ARG EMULATOR_RPM_SHA256=6b29b9342fa6457017612d5a3a211dbfb97b1bc01a34a8e2c893e3b29ae30955
# Key file whose fingerprint was checked against the documented 98BC F336 A3BE 53B7 34E9 67C5 2E5B F49B D940 F624.
ARG EMULATOR_KEY_SHA256=33f40fa3b822167ba2139368242a220bf9c8d753044947fa83bb1db1fd04b9ad

ADD https://downloads.aws.com/aws-emulator/packages/aws-emulator/LTS/latest/aws-emulator-aarch64.rpm /tmp/aws-emulator.rpm
ADD https://downloads.aws.com/keys/gpg/current.asc /tmp/current.asc

RUN echo "${EMULATOR_RPM_SHA256}  /tmp/aws-emulator.rpm" | sha256sum -c - \
    && echo "${EMULATOR_KEY_SHA256}  /tmp/current.asc" | sha256sum -c - \
    && rpm --import /tmp/current.asc \
    && rpm -K /tmp/aws-emulator.rpm \
    && rpm -i /tmp/aws-emulator.rpm \
    && test "$(rpm -q --qf '%{VERSION}' aws-emulator)" = "${EMULATOR_VERSION}" \
    && rm /tmp/aws-emulator.rpm /tmp/current.asc \
    && mkdir -p /home/emulator && chown 1000 /home/emulator

USER 1000
ENV HOME=/home/emulator
EXPOSE 9297
ENTRYPOINT ["aws-emulator", "-b", "0.0.0.0"]
