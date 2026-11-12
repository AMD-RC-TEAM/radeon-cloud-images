# upstream: docker.io/rocm/pytorch:rocm7.14.1_ubuntu24.04_py3.12_pytorch_release_2.12.0@sha256:cc9b00f90b85c97b015b040fa55c8d1b404b7cacc6ad57d74ee3451c97508da1
# A FROM-only Dockerfile is released as the mirrored upstream image itself (same digest).
# Add RUN/COPY lines below to build our own layer on top; the pipeline then builds with Kaniko.
FROM 10.5.10.12:1808/radeon-cloud-global/rocm/pytorch@sha256:cc9b00f90b85c97b015b040fa55c8d1b404b7cacc6ad57d74ee3451c97508da1
