from strikecast_core.evaluation.metrics import evaluate_binary_classifier

if __name__ == "__main__":
    y_true = [0, 0, 1, 1, 1, 0, 1, 0]
    probabilities = [0.08, 0.22, 0.71, 0.84, 0.62, 0.31, 0.57, 0.18]
    print(evaluate_binary_classifier(y_true, probabilities))
