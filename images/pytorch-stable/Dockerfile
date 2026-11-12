# upstream: docker.io/rocm/pytorch:rocm7.2.4_ubuntu24.04_py3.12_pytorch_release_2.10.0@sha256:4449f856653602317e4101a76fce599c7fcd58ccec2e539951fce5f73083179e
# A FROM-only Dockerfile is released as the mirrored upstream image itself (same digest).
# Add RUN/COPY lines below to build our own layer on top; the pipeline then builds with Kaniko.
FROM 10.5.10.12:1808/radeon-cloud-global/rocm/pytorch@sha256:4449f856653602317e4101a76fce599c7fcd58ccec2e539951fce5f73083179e
