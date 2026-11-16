// Time-conditioned covariance of 4D Gaussians and its analytic gradient.
//
// For unit quaternions l and r, the 4D rotation is R = L(l) Q(r), where L and Q
// are the left and right isoclinic matrices below. With F = R diag(s), the joint
// covariance is S = F F^T. Writing c = S[0:3, 3] and t = S[3, 3], conditioning
// on time gives
//     spatial  = S[0:3, 0:3] - c c^T / t   (stored as xx, xy, xz, yy, yz, zz)
//     velocity = c / t
//     variance = t.
// This matches covariance4() in gaussian.py, the float64 test reference, except
// that F.normalize clamps quaternion norms below 1e-12; zero quaternions are invalid here.

namespace conditional {

// Entry e = 4 i + j of L(l) is sign * l[i ^ j]; Q(r) shares the component
// pattern. Set bits mark negative signs. All indices fold at compile time.
__device__ __forceinline__ constexpr int component(int e) { return (e >> 2) ^ (e & 3); }
__device__ __forceinline__ constexpr float left_sign(int e) { return (0x284E >> e) & 1 ? -1.f : 1.f; }
__device__ __forceinline__ constexpr float right_sign(int e) { return (0x3950 >> e) & 1 ? -1.f : 1.f; }
// Packed upper-triangular 3x3 entry k: xx, xy, xz, yy, yz, zz.
__device__ __forceinline__ constexpr int row(int k) { return k < 3 ? 0 : (k < 5 ? 1 : 2); }
__device__ __forceinline__ constexpr int col(int k) { return k < 3 ? k : (k < 5 ? k - 2 : 2); }

struct Geometry {
    float left[4], right[4];    // normalized quaternions
    float left_norm, right_norm;
    float L[16], Q[16], R[16];  // row-major 4x4
    float F[16];                // R diag(s)
    float S[16];                // F F^T
};

__device__ __forceinline__ void normalize(const float* q, float* unit, float& norm) {
    norm = sqrtf(q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3]);
    #pragma unroll
    for (int k = 0; k < 4; ++k) unit[k] = q[k] / norm;
}

__device__ __forceinline__ void build(const float* scale, const float* left, const float* right, Geometry& g) {
    normalize(left, g.left, g.left_norm);
    normalize(right, g.right, g.right_norm);
    #pragma unroll
    for (int e = 0; e < 16; ++e) {
        g.L[e] = left_sign(e) * g.left[component(e)];
        g.Q[e] = right_sign(e) * g.right[component(e)];
    }
    #pragma unroll
    for (int i = 0; i < 4; ++i)
        #pragma unroll
        for (int j = 0; j < 4; ++j) {
            float sum = 0.f;
            #pragma unroll
            for (int k = 0; k < 4; ++k) sum += g.L[i * 4 + k] * g.Q[k * 4 + j];
            g.R[i * 4 + j] = sum;
            g.F[i * 4 + j] = sum * scale[j];
        }
    #pragma unroll
    for (int i = 0; i < 4; ++i)
        #pragma unroll
        for (int j = i; j < 4; ++j) {
            float sum = 0.f;
            #pragma unroll
            for (int k = 0; k < 4; ++k) sum += g.F[i * 4 + k] * g.F[j * 4 + k];
            g.S[i * 4 + j] = sum;
            g.S[j * 4 + i] = sum;
        }
}

__global__ void forward(int n, const float* scale, const float* left, const float* right,
                        float* spatial, float* velocity, float* variance) {
    const int p = blockIdx.x * blockDim.x + threadIdx.x;
    if (p >= n) return;
    Geometry g;
    build(scale + 4 * p, left + 4 * p, right + 4 * p, g);
    const float t = g.S[15];
    const float c[3] = {g.S[3], g.S[7], g.S[11]};
    float v[3];
    #pragma unroll
    for (int i = 0; i < 3; ++i) v[i] = c[i] / t;
    #pragma unroll
    for (int k = 0; k < 6; ++k) {
        const int i = row(k), j = col(k);
        spatial[6 * p + k] = g.S[i * 4 + j] - c[i] * v[j];
    }
    #pragma unroll
    for (int i = 0; i < 3; ++i) velocity[3 * p + i] = v[i];
    variance[p] = t;
}

__global__ void backward(int n, const float* scale, const float* left, const float* right,
                         const float* grad_spatial, const float* grad_velocity, const float* grad_variance,
                         float* grad_scale, float* grad_left, float* grad_right) {
    const int p = blockIdx.x * blockDim.x + threadIdx.x;
    if (p >= n) return;
    Geometry g;
    build(scale + 4 * p, left + 4 * p, right + 4 * p, g);
    const float t = g.S[15];
    const float c[3] = {g.S[3], g.S[7], g.S[11]};
    const float* gp = grad_spatial + 6 * p;
    const float* gv = grad_velocity + 3 * p;

    // Symmetric G with dL = sum_ij G_ij d(spatial)_ij; packed off-diagonals count twice.
    float G[9];
    #pragma unroll
    for (int k = 0; k < 6; ++k) {
        const int i = row(k), j = col(k);
        const float value = i == j ? gp[k] : 0.5f * gp[k];
        G[i * 3 + j] = value;
        G[j * 3 + i] = value;
    }
    // Gradients with respect to the cross-covariance c and the temporal variance t.
    float Gc[3], cGc = 0.f, gv_c = 0.f;
    #pragma unroll
    for (int i = 0; i < 3; ++i) {
        Gc[i] = G[i * 3 + 0] * c[0] + G[i * 3 + 1] * c[1] + G[i * 3 + 2] * c[2];
        cGc += c[i] * Gc[i];
        gv_c += gv[i] * c[i];
    }
    const float inv_t = 1.f / t;
    float dc[3];
    #pragma unroll
    for (int i = 0; i < 3; ++i) dc[i] = (gv[i] - 2.f * Gc[i]) * inv_t;
    const float dt = grad_variance[p] + (cGc - gv_c) * inv_t * inv_t;

    // Symmetric H with dL = sum_ij H_ij dS_ij over all 16 entries of S.
    float H[16];
    #pragma unroll
    for (int i = 0; i < 3; ++i) {
        #pragma unroll
        for (int j = 0; j < 3; ++j) H[i * 4 + j] = G[i * 3 + j];
        H[i * 4 + 3] = 0.5f * dc[i];
        H[12 + i] = 0.5f * dc[i];
    }
    H[15] = dt;

    // S = F F^T  =>  dL/dF = 2 H F.  F = R diag(s).
    float dR[16];
    float ds[4] = {0.f, 0.f, 0.f, 0.f};
    #pragma unroll
    for (int i = 0; i < 4; ++i)
        #pragma unroll
        for (int j = 0; j < 4; ++j) {
            float dF = 0.f;
            #pragma unroll
            for (int k = 0; k < 4; ++k) dF += H[i * 4 + k] * g.F[k * 4 + j];
            dF *= 2.f;
            ds[j] += dF * g.R[i * 4 + j];
            dR[i * 4 + j] = dF * scale[4 * p + j];
        }
    #pragma unroll
    for (int j = 0; j < 4; ++j) grad_scale[4 * p + j] = ds[j];

    // R = L Q  =>  dL/dL = dR Q^T and dL/dQ = L^T dR.
    float dl[4] = {0.f, 0.f, 0.f, 0.f}, dq[4] = {0.f, 0.f, 0.f, 0.f};
    #pragma unroll
    for (int i = 0; i < 4; ++i)
        #pragma unroll
        for (int j = 0; j < 4; ++j) {
            float dLij = 0.f, dQij = 0.f;
            #pragma unroll
            for (int k = 0; k < 4; ++k) {
                dLij += dR[i * 4 + k] * g.Q[j * 4 + k];
                dQij += g.L[k * 4 + i] * dR[k * 4 + j];
            }
            const int e = i * 4 + j;
            dl[component(e)] += left_sign(e) * dLij;
            dq[component(e)] += right_sign(e) * dQij;
        }

    // Through normalization u = q / |q|: dq = (du - u (u . du)) / |q|.
    float u_dl = 0.f, u_dq = 0.f;
    #pragma unroll
    for (int k = 0; k < 4; ++k) {
        u_dl += g.left[k] * dl[k];
        u_dq += g.right[k] * dq[k];
    }
    #pragma unroll
    for (int k = 0; k < 4; ++k) {
        grad_left[4 * p + k] = (dl[k] - g.left[k] * u_dl) / g.left_norm;
        grad_right[4 * p + k] = (dq[k] - g.right[k] * u_dq) / g.right_norm;
    }
}

}  // namespace conditional
