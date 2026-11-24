. /floor/smoke_lib.sh
echo "== unset (expect FAIL)"; ( unset TORCH_BLAS_PREFER_HIPBLASLT; torch_gemm_floor ) && echo "RESULT unset PASS" || echo "RESULT unset FAIL"
echo "== =0 (expect PASS)"; ( export TORCH_BLAS_PREFER_HIPBLASLT=0; torch_gemm_floor ) && echo "RESULT zero PASS" || echo "RESULT zero FAIL"
