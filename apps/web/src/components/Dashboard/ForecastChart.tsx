interface ForecastChartProps {
  forecastText: string;
  horizonMinutes: number;
}

function ForecastChart({
  forecastText,
  horizonMinutes,
}: ForecastChartProps) {
  return (
    <div className="card">
      <p className="card-label">RISK FORECAST</p>

      <div className="forecast-summary">
        <div className="forecast-horizon">
          NEXT {horizonMinutes} MINUTES
        </div>

        <p className="forecast-text">
          {forecastText}
        </p>
      </div>
    </div>
  );
}

export default ForecastChart;
