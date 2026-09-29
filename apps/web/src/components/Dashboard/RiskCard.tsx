import type { PredictionResponse } from "../../types/prediction";

interface RiskCardProps {
  prediction: PredictionResponse | null;
  loading: boolean;
}

function RiskCard({
  prediction,
  loading,
}: RiskCardProps) {
  if (loading) {
    return (
      <div className="card">
        <p className="card-label">CONVECTIVE RISK</p>
        <h2 className="risk-level">
          ANALYZING
        </h2>
        <p className="muted">
          Querying M5 prediction API...
        </p>
      </div>
    );
  }

  if (!prediction) {
    return (
      <div className="card">
        <p className="card-label">CONVECTIVE RISK</p>
        <h2 className="risk-level">--</h2>
        <p className="probability">--%</p>
        <p className="muted">
          Select a location on the map
        </p>
      </div>
    );
  }

  return (
    <div className="card">
      <p className="card-label">
        CONVECTIVE RISK
      </p>

      <h2
        className={`risk-level risk-${prediction.riskLevel.toLowerCase()}`}
      >
        {prediction.riskLevel}
      </h2>

      <p className="probability">
        {prediction.riskProbability}%
      </p>

      <p className="muted">
        Prediction probability
      </p>

      <div className="confidence">
        Model confidence:{" "}
        <strong>
          {prediction.confidence}%
        </strong>
      </div>

      <div className="model-meta">
        <span>
          {prediction.modelName}
        </span>
        <span>
          v{prediction.modelVersion}
        </span>
      </div>

      <div className="demo-badge trained-badge">TRAINED CONVLSTM</div>
    </div>
  );
}

export default RiskCard;
