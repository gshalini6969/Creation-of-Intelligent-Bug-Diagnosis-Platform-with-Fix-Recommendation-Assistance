import { Link } from "react-router-dom";
import "./HomePage.css";

const WORKFLOW_STEPS = [
  "Submit Bug",
  "Analyze",
  "Retrieve Similar Historical Bugs",
  "Identify Root Cause",
  "Recommend Fix",
];

const FEATURES = [
  {
    title: "Bug Diagnosis",
    description: "Parses raw error logs and stack traces to extract exception type, language, file, and line.",
  },
  {
    title: "Historical Knowledge",
    description: "Every submitted bug becomes part of a searchable, growing knowledge base.",
  },
  {
    title: "Similar Bug Detection",
    description: "Finds related historical bugs even when the wording differs, using concept-aware matching.",
  },
  {
    title: "Root Cause Analysis",
    description: "Rule-based diagnosis distinguishes real causes instead of collapsing everything into one bucket.",
  },
  {
    title: "Fix Recommendation",
    description: "Suggests concrete next steps, prioritizing confirmed fixes from resolved historical bugs.",
  },
];

export default function HomePage() {
  return (
    <div className="home-page">
      <section className="home-hero">
        <h1>Creation of Intelligent Bug Diagnosis Platform with Fix Recommendation Assistance</h1>
        <p className="home-hero__subtitle">
          Creation of Intelligent Bug Diagnosis Platform with Fix Recommendation Assistance
        </p>
        <p className="home-hero__description">
          Analyzes bug reports and error logs, identifies probable root causes,
          searches historical bugs for related issues, and recommends fixes
          grounded in what actually resolved similar problems before.
        </p>
        <div className="home-hero__actions">
          <Link className="home-btn home-btn--primary" to="/analyze-bug">
            Analyze a Bug
          </Link>
          <Link className="home-btn home-btn--secondary" to="/submit-bug">
            Submit a Bug
          </Link>
        </div>
      </section>

      <section className="home-workflow">
        <h2>How It Works</h2>
        <ol className="home-workflow__steps">
          {WORKFLOW_STEPS.map((step, index) => (
            <li key={step} className="home-workflow__step">
              <span className="home-workflow__step-number">{index + 1}</span>
              <span>{step}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="home-features">
        <h2>Core Capabilities</h2>
        <div className="home-features__grid">
          {FEATURES.map((feature) => (
            <div key={feature.title} className="home-feature-card">
              <h3>{feature.title}</h3>
              <p>{feature.description}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="home-cta">
        <h2>Ready to investigate a bug?</h2>
        <Link className="home-btn home-btn--primary" to="/analyze-bug">
          Analyze Bug
        </Link>
      </section>
    </div>
  );
}
