# Machine Learning Directory

The notebooks in `notebooks/` (such as `01_kaggle_model_comparison.ipynb`) are strictly for exploratory data analysis, feature experimentation, and initial model evaluation. They are not used to produce deployed artifacts and should never contain committed outputs or local execution metadata. Developers should run `nbstripout --install` once in their local Git environment to automatically strip outputs on commit.

Production models are built and registered exclusively through reproducible Django management commands (`python app/manage.py train_model_a` added in Task A14, and `train_model_b` added in Task A18). These pipelines enforce strict feature validation, evaluate models against naive baselines, and save audited metrics alongside each model version.

All trained model binaries (`*.pkl`, `*.joblib`) and raw datasets (`*.csv`) live strictly outside Git in the directory specified by the `MODEL_ARTIFACT_DIR` environment variable. The application serves models through a dedicated registry and `PredictorService`.
