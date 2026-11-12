from __future__ import annotations

import numpy as np
from scipy.optimize import minimize


MODELS = ("M0", "M1", "M2")


def stable_softmax(eta: np.ndarray) -> np.ndarray:
    z = eta - eta.max(
        axis=1,
        keepdims=True,
    )

    exp_z = np.exp(z)

    return (
        exp_z
        / exp_z.sum(
            axis=1,
            keepdims=True,
        )
    )


def build_x(
    log_market: np.ndarray,
    log_weather: np.ndarray,
    model: str,
) -> np.ndarray:
    if model == "M0":
        return log_market[:, :, None]

    if model == "M1":
        return log_weather[:, :, None]

    if model == "M2":
        return np.stack(
            [
                log_market,
                log_weather,
            ],
            axis=2,
        )

    raise ValueError(
        f"Unknown model: {model}"
    )


def unpack_params(
    theta: np.ndarray,
    p: int,
):
    intercepts = np.zeros(6)

    intercepts[1:] = theta[:5]

    beta = theta[
        5:5 + p
    ]

    return intercepts, beta


def objective_and_gradient(
    theta: np.ndarray,
    x: np.ndarray,
    y_idx: np.ndarray,
    lam: float,
):
    n, k, p = x.shape

    intercepts, beta = unpack_params(
        theta,
        p,
    )

    eta = (
        intercepts[None, :]
        + np.einsum(
            "nkp,p->nk",
            x,
            beta,
        )
    )

    probs = stable_softmax(eta)

    winner_prob = probs[
        np.arange(n),
        y_idx,
    ]

    nll = -np.mean(
        np.log(winner_prob)
    )

    penalty = (
        0.5
        * lam
        * np.dot(beta, beta)
    )

    loss = nll + penalty

    residual = probs.copy()

    residual[
        np.arange(n),
        y_idx,
    ] -= 1.0

    residual /= n

    grad_intercepts = (
        residual[:, 1:]
        .sum(axis=0)
    )

    grad_beta = np.einsum(
        "nk,nkp->p",
        residual,
        x,
    )

    grad_beta += (
        lam * beta
    )

    grad = np.concatenate(
        [
            grad_intercepts,
            grad_beta,
        ]
    )

    return loss, grad


def fit_model(
    log_market: np.ndarray,
    log_weather: np.ndarray,
    y_idx: np.ndarray,
    model: str,
    lam: float,
):
    x = build_x(
        log_market,
        log_weather,
        model,
    )

    p = x.shape[2]

    theta0 = np.zeros(
        5 + p,
        dtype=float,
    )

    result = minimize(
        fun=lambda theta:
            objective_and_gradient(
                theta,
                x,
                y_idx,
                lam,
            ),
        x0=theta0,
        method="L-BFGS-B",
        jac=True,
        options={
            "maxiter": 2000,
            "ftol": 1e-12,
            "gtol": 1e-8,
        },
    )

    if not result.success:
        raise RuntimeError(
            f"{model}, lambda={lam}: "
            f"optimizer failed: "
            f"{result.message}"
        )

    return result.x, result


def predict_model(
    theta: np.ndarray,
    log_market: np.ndarray,
    log_weather: np.ndarray,
    model: str,
) -> np.ndarray:
    x = build_x(
        log_market,
        log_weather,
        model,
    )

    p = x.shape[2]

    intercepts, beta = unpack_params(
        theta,
        p,
    )

    eta = (
        intercepts[None, :]
        + np.einsum(
            "nkp,p->nk",
            x,
            beta,
        )
    )

    return stable_softmax(eta)


def coefficient_dict(
    theta: np.ndarray,
    model: str,
) -> dict:
    if model in ("M0", "M1"):
        p = 1
    else:
        p = 2

    intercepts, beta = unpack_params(
        theta,
        p,
    )

    out = {
        f"bucket_{k}_intercept":
            float(intercepts[k - 1])
        for k in range(1, 7)
    }

    if model == "M0":
        out["beta_market"] = float(
            beta[0]
        )

    elif model == "M1":
        out["beta_weather"] = float(
            beta[0]
        )

    elif model == "M2":
        out["beta_market"] = float(
            beta[0]
        )
        out["beta_weather"] = float(
            beta[1]
        )

    return out
