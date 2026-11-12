# upstream: docker.io/rocm/pytorch:rocm10.1.0_ubuntu24.04_py3.12_pytorch_release_2.14.0@sha256:099f59a3bee9c436f5cc57db6bc6076fdeda579c57e9e22ae40f856d5905b3e4
# A FROM-only Dockerfile is released as the mirrored upstream image itself (same digest).
# Add RUN/COPY lines below to build our own layer on top; the pipeline then builds with Kaniko.
FROM 10.5.10.12:1808/radeon-cloud-global/rocm/pytorch@sha256:099f59a3bee9c436f5cc57db6bc6076fdeda579c57e9e22ae40f856d5905b3e4
