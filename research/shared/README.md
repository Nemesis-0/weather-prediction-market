# Shared historical research components

The V1/V2 historical experiments reused several data-construction and feature-processing components. They are organized here to make cross-study dependencies explicit without duplicating the underlying code.

| Component | Role |
|:--|:--|
| [Market data](code/market/) | Kalshi historical market acquisition, candle construction and panel assembly |
| [Weather data](code/weather/) | NOAA/NBM forecast acquisition, weather-state processing and quality checks |
| [Feature assembly](code/modeling/) | Historical modeling-feature generation used by the earlier experiments |
| [Cross-study documentation](docs/) | Original shared research protocols, contract interpretation and technical reference material |

These are **historical** components. The V1/V2 final outcomes and frozen specifications live within their respective studies, and the prospective IBKR / ForecastEx V3 modules reside in [V3](../v3/README.md).

[← Research index](../README.md) · [Data sources and limitations](../../DATA_POLICY.md)
