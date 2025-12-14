"""
Test Predictions Script
Load the trained model and test predictions on new emails.

Usage: python test_predictions.py
"""
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from train_local import LocalReplyPredictor

# ============================================================
# CONFIGURATION - UPDATE MODEL PATH IF NEEDED
# ============================================================
MODEL_DIR = "models/20251212_045113"  # Latest trained model
# ============================================================


def find_latest_model():
    """Find the latest model in the models directory."""
    models_dir = Path("models")
    if not models_dir.exists():
        return None
    
    model_dirs = [d for d in models_dir.iterdir() if d.is_dir() and (d / "model_metadata.json").exists()]
    if not model_dirs:
        return None
    
    # Sort by name (which is timestamp-based) and get latest
    latest = sorted(model_dirs, reverse=True)[0]
    return str(latest)


def test_single_prediction(model, subject, name="", email=""):
    """Test a single prediction and print results."""
    result = model.predict_single(subject, name, email)
    
    print(f"\nSubject: {subject}")
    if name:
        print(f"Recipient: {name} <{email}>")
    print(f"  Reply Probability: {result['reply_probability']}%")
    print(f"  Will Reply: {'YES' if result['will_reply'] else 'NO'}")
    print(f"  Confidence: {result['confidence']}%")
    
    return result


def run_batch_tests(model):
    """Run batch tests on various email subjects."""
    print("\n" + "="*70)
    print("BATCH PREDICTIONS")
    print("="*70)
    
    test_cases = [
        # Sales/Marketing emails (typically lower reply rate)
        ("Exclusive offer: 50% off today only!", "Sales Lead", "sales@company.com"),
        ("Check out our new product launch", "Marketing Person", "marketing@corp.com"),
        ("Limited time discount for you", "Promo Target", "promo@email.com"),
        
        # Professional/Business emails (typically higher reply rate)
        ("Meeting request for next week", "John Smith", "john@business.com"),
        ("Follow-up on our call yesterday", "Sarah Johnson", "sarah@company.org"),
        ("Quick question about the project", "Mike Wilson", "mike@tech.io"),
        ("Can we schedule a call?", "Lisa Brown", "lisa@startup.com"),
        
        # Internal/Update emails (medium reply rate)
        ("Important update: System maintenance", "IT Team", "it@internal.net"),
        ("Your feedback is needed on proposal", "Team Lead", "lead@company.com"),
        ("Re: Previous discussion", "Colleague", "colleague@work.com"),
        
        # Cold outreach (typically lower reply rate)
        ("Introduction from [Company Name]", "Cold Lead", "cold@prospect.com"),
        ("I'd love to connect", "Networker", "network@linkedin.com"),
        
        # Personalized emails (typically higher reply rate)
        ("Saw your talk at the conference", "Fan", "fan@event.com"),
        ("Regarding your recent blog post", "Reader", "reader@blog.com"),
    ]
    
    print(f"\n{'Subject':<50} {'Probability':<12} {'Reply?':<8} {'Confidence'}")
    print("-" * 85)
    
    results = []
    for subject, name, email in test_cases:
        result = model.predict_single(subject, name, email)
        reply_str = "YES" if result['will_reply'] else "NO"
        print(f"{subject[:48]:<50} {result['reply_probability']:>8.1f}%    {reply_str:<8} {result['confidence']:.1f}%")
        results.append(result)
    
    return results


def interactive_mode(model):
    """Interactive mode for testing custom emails."""
    print("\n" + "="*70)
    print("INTERACTIVE PREDICTION MODE")
    print("="*70)
    print("\nEnter email details to predict reply probability.")
    print("Type 'quit' or 'exit' to stop.\n")
    
    while True:
        try:
            subject = input("Email Subject: ").strip()
            if subject.lower() in ['quit', 'exit', 'q']:
                print("\nExiting interactive mode.")
                break
            
            if not subject:
                print("Please enter a subject line.\n")
                continue
            
            name = input("Recipient Name (optional): ").strip()
            email = input("Recipient Email (optional): ").strip()
            
            result = model.predict_single(subject, name, email)
            
            print("\n" + "-"*50)
            print(f"PREDICTION RESULT")
            print("-"*50)
            print(f"  Subject: {subject}")
            if name:
                print(f"  Recipient: {name} <{email}>")
            print(f"\n  Reply Probability: {result['reply_probability']}%")
            print(f"  Prediction: {'WILL REPLY' if result['will_reply'] else 'WILL NOT REPLY'}")
            print(f"  Confidence: {result['confidence']}%")
            
            if result['reply_probability'] >= 70:
                print("\n  >> HIGH chance of reply - Good candidate!")
            elif result['reply_probability'] >= 50:
                print("\n  >> MEDIUM chance of reply - Worth trying")
            elif result['reply_probability'] >= 30:
                print("\n  >> LOW chance of reply - May need better subject")
            else:
                print("\n  >> VERY LOW chance - Consider revising the email")
            
            print("-"*50 + "\n")
            
        except KeyboardInterrupt:
            print("\n\nExiting interactive mode.")
            break


def main():
    """Main function."""
    print("\n" + "="*70)
    print("  EMAIL REPLY PREDICTION TESTER")
    print("="*70)
    
    # Find model
    model_dir = MODEL_DIR
    if not os.path.exists(model_dir):
        print(f"\nModel not found at: {model_dir}")
        print("Looking for latest model...")
        model_dir = find_latest_model()
        
        if not model_dir:
            print("\n[ERROR] No trained model found!")
            print("Please run 'python train_local.py' first to train a model.")
            sys.exit(1)
    
    print(f"\nLoading model from: {model_dir}")
    
    # Load model
    try:
        model = LocalReplyPredictor.load(model_dir)
        print("[OK] Model loaded successfully!")
    except Exception as e:
        print(f"\n[ERROR] Failed to load model: {e}")
        sys.exit(1)
    
    # Run batch tests
    run_batch_tests(model)
    
    # Summary
    print("\n" + "="*70)
    print("MODEL INTERPRETATION GUIDE")
    print("="*70)
    print("""
    Reply Probability:
      70-100%  : HIGH    - Strong chance of getting a reply
      50-69%   : MEDIUM  - Decent chance, worth sending
      30-49%   : LOW     - May want to improve subject/timing
      0-29%    : VERY LOW - Consider revising the approach
    
    Confidence:
      Higher confidence = model is more certain about its prediction
      Lower confidence = prediction is less certain (close to 50/50)
    
    Tips for Higher Reply Rates:
      - Use questions in subject lines
      - Be specific about the topic
      - Avoid overly salesy language
      - Personalize when possible
      - Keep subject lines concise
    """)
    
    # Ask for interactive mode (only if running interactively)
    print("\n" + "="*70)
    if sys.stdin.isatty():
        try:
            choice = input("\nWould you like to test custom emails interactively? (y/n): ").strip().lower()
            if choice in ['y', 'yes']:
                interactive_mode(model)
        except (KeyboardInterrupt, EOFError):
            pass
    else:
        print("\nRun this script directly for interactive mode.")
    
    print("\n[DONE] Testing complete!")


if __name__ == "__main__":
    main()




