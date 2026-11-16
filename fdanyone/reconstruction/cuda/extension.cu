#include <torch/extension.h>
#include <ATen/cuda/CUDAContext.h>
#include <c10/cuda/CUDAGuard.h>
#include <c10/cuda/CUDAException.h>
#include "conditional.cuh"
#include "adam.cuh"

using Tensor = torch::Tensor;

void check(const Tensor& t, const Tensor& reference) {
    TORCH_CHECK(t.is_cuda() && t.scalar_type() == torch::kFloat32 && t.is_contiguous(),
                "4DGS kernels require contiguous CUDA float32 tensors");
    TORCH_CHECK(t.device() == reference.device(), "4DGS tensors must share a device");
}

void check_geometry(const Tensor& s, const Tensor& l, const Tensor& r) {
    for (const auto& t : {s, l, r}) {
        check(t, s);
        TORCH_CHECK(t.dim() == 2 && t.size(1) == 4 && t.size(0) == s.size(0), "Expected N x 4");
    }
}

std::vector<Tensor> covariance(Tensor s, Tensor l, Tensor r) {
    check_geometry(s, l, r);
    c10::cuda::CUDAGuard guard(s.device());
    const int n = s.size(0);
    auto cov = torch::empty({n, 6}, s.options());
    auto velocity = torch::empty({n, 3}, s.options());
    auto variance = torch::empty({n, 1}, s.options());
    if (n) {
        conditional::forward<<<(n + 255) / 256, 256, 0, at::cuda::getCurrentCUDAStream()>>>(
            n, s.data_ptr<float>(), l.data_ptr<float>(), r.data_ptr<float>(), cov.data_ptr<float>(),
            velocity.data_ptr<float>(), variance.data_ptr<float>());
        C10_CUDA_KERNEL_LAUNCH_CHECK();
    }
    return {cov, velocity, variance};
}

std::vector<Tensor> covariance_backward(Tensor s, Tensor l, Tensor r, Tensor dc, Tensor dv, Tensor dt) {
    check_geometry(s, l, r);
    const int n = s.size(0);
    for (const auto& t : {dc, dv, dt}) check(t, s);
    TORCH_CHECK(dc.sizes() == torch::IntArrayRef({n, 6}) &&
                dv.sizes() == torch::IntArrayRef({n, 3}) &&
                dt.sizes() == torch::IntArrayRef({n, 1}), "Invalid covariance gradients");
    c10::cuda::CUDAGuard guard(s.device());
    auto ds = torch::empty_like(s), dl = torch::empty_like(l), dr = torch::empty_like(r);
    if (n) {
        conditional::backward<<<(n + 255) / 256, 256, 0, at::cuda::getCurrentCUDAStream()>>>(
            n, s.data_ptr<float>(), l.data_ptr<float>(), r.data_ptr<float>(), dc.data_ptr<float>(),
            dv.data_ptr<float>(), dt.data_ptr<float>(), ds.data_ptr<float>(), dl.data_ptr<float>(),
            dr.data_ptr<float>());
        C10_CUDA_KERNEL_LAUNCH_CHECK();
    }
    return {ds, dl, dr};
}

void adam(Tensor p, Tensor g, Tensor m, Tensor v, float step, float lr) {
    for (const auto& t : {p, g, m, v}) {
        check(t, p);
        TORCH_CHECK(t.sizes() == p.sizes(), "Invalid Adam tensor shape");
    }
    c10::cuda::CUDAGuard guard(p.device());
    const int64_t n = p.numel();
    TORCH_CHECK(n <= INT_MAX, "Adam tensor is too large");
    if (n) {
        adam_kernel<<<(n + 255) / 256, 256, 0, at::cuda::getCurrentCUDAStream()>>>(
            p.data_ptr<float>(), g.data_ptr<float>(), m.data_ptr<float>(), v.data_ptr<float>(),
            step, 0.9f, 0.999f, lr, 1e-15f, n);
        C10_CUDA_KERNEL_LAUNCH_CHECK();
    }
}

PYBIND11_MODULE(TORCH_EXTENSION_NAME, m) {
    m.def("covariance", &covariance);
    m.def("covariance_backward", &covariance_backward);
    m.def("adam", &adam);
}
