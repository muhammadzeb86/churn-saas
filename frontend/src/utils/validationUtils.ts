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
 * Parse risk/protective factors from backend JSON format
 * Backend sends: [{"factor": "...", "impact": "...", "message": "..."}]
 * Frontend needs: ["message 1", "message 2", ...]
 */
export const parseFactors = (value: unknown): string[] => {
  if (!value) return [];
  
  try {
    let parsed: unknown;
    
    // If already an array, use it
    if (Array.isArray(value)) {
      parsed = value;
    } 
    // If string, try to parse JSON
    else if (typeof value === 'string') {
      parsed = JSON.parse(value);
    } 
    else {
      return [];
    }
    
    // Validate it's an array
    if (!Array.isArray(parsed)) {
      return [];
    }
    
    // Extract messages from factor objects
    return parsed
      .filter(item => item && typeof item === 'object' && 'message' in item)
      .map(item => (item as { message: string }).message)
      .filter(msg => typeof msg === 'string' && msg.length > 0);
  } catch (error) {
    console.warn('Failed to parse factors:', error);
    return [];
  }
};

/**
 * Parse explanation JSON from backend
 * Backend sends: {"customer_id": "...", "summary": "...", "risk_level": "..."}
 * Frontend needs: Extract the summary text
 */
export const parseExplanation = (value: unknown): { summary: string; riskLevel: string } | null => {
  if (!value) return null;
  
  try {
    let parsed: unknown;
    
    // If already an object, use it
    if (typeof value === 'object' && value !== null) {
      parsed = value;
    } 
    // If string, try to parse JSON
    else if (typeof value === 'string') {
      parsed = JSON.parse(value);
    } 
    else {
      return null;
    }
    
    // Validate it has summary
    if (parsed && typeof parsed === 'object' && 'summary' in parsed) {
      const obj = parsed as { summary?: string; risk_level?: string };
      return {
        summary: obj.summary || '',
        riskLevel: obj.risk_level || 'Unknown'
      };
    }
    
    return null;
  } catch (error) {
    console.warn('Failed to parse explanation:', error);
    return null;
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

