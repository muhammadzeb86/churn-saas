/**
 * Safely parse and validate JSON arrays of strings
 * Prevents arbitrary code execution from malformed data
 */
export const parseStringArray = (value: unknown): string[] => {
  if (!value) return [];
  
  try {
    let parsed: unknown;
    
    // If already an array, use it
    if (Array.isArray(value)) {
      parsed = value;
    } 
    // If string, try to parse
    else if (typeof value === 'string') {
      parsed = JSON.parse(value);
    } 
    else {
      return [];
    }
    
    // Validate it's an array of strings
    if (Array.isArray(parsed) && parsed.every(item => typeof item === 'string')) {
      return parsed;
    }
    
    return [];
  } catch (error) {
    console.warn('Failed to parse array:', error);
    return [];
  }
};

/**
 * Validate prediction object has required fields
 */
export const validatePrediction = (pred: any): boolean => {
  return (
    pred &&
    typeof pred.id === 'string' &&
    typeof pred.churn_probability === 'number' &&
    !isNaN(pred.churn_probability) &&
    pred.churn_probability >= 0 &&
    pred.churn_probability <= 1 &&
    typeof pred.created_at === 'string'
  );
};

