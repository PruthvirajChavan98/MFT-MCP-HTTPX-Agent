import { useState } from "react";
import { Cpu, DollarSign, Hash, Layers, ArrowRight, Play, Loader2 } from "lucide-react";
import { mockModels } from "../../lib/api";

export function ModelsPage() {
  const [models] = useState(mockModels);
  const [classifyInput, setClassifyInput] = useState("");
  const [classifyResult, setClassifyResult] = useState<null | {
    category: string;
    confidence: number;
    mode: string;
    reasoning: string;
  }>(null);
  const [isClassifying, setIsClassifying] = useState(false);

  const handleClassify = () => {
    if (!classifyInput.trim()) return;
    setIsClassifying(true);
    // Simulate classification
    setTimeout(() => {
      const categories = ["faq_retrieval", "general_query", "off_topic", "comparison_query", "account_services"];
      const cat = categories[Math.floor(Math.random() * categories.length)];
      setClassifyResult({
        category: cat,
        confidence: 0.8 + Math.random() * 0.19,
        mode: "hybrid",
        reasoning: `Query matched ${cat.replace(/_/g, " ")} pattern with high confidence based on semantic + keyword analysis.`,
      });
      setIsClassifying(false);
    }, 800);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-gray-900" style={{ fontWeight: 700 }}>Models & Router</h1>
        <p className="text-gray-500" style={{ fontSize: 14 }}>Model catalog & NBFC router classification tool</p>
      </div>

      {/* Model Catalog */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100">
          <h3 className="text-gray-900" style={{ fontWeight: 600 }}>Model Catalog</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="text-left px-5 py-3 text-gray-500" style={{ fontSize: 12, fontWeight: 500 }}>Model</th>
                <th className="text-left px-5 py-3 text-gray-500" style={{ fontSize: 12, fontWeight: 500 }}>ID</th>
                <th className="text-left px-5 py-3 text-gray-500" style={{ fontSize: 12, fontWeight: 500 }}>Context Length</th>
                <th className="text-left px-5 py-3 text-gray-500" style={{ fontSize: 12, fontWeight: 500 }}>Input Cost</th>
                <th className="text-left px-5 py-3 text-gray-500" style={{ fontSize: 12, fontWeight: 500 }}>Output Cost</th>
              </tr>
            </thead>
            <tbody>
              {models.map((model) => (
                <tr key={model.id} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: "var(--brand-gradient)" }}>
                        <Cpu className="w-4 h-4 text-white" />
                      </div>
                      <span className="text-gray-900" style={{ fontSize: 13, fontWeight: 500 }}>{model.name}</span>
                    </div>
                  </td>
                  <td className="px-5 py-3">
                    <code className="text-brand-dark bg-brand-light/10 px-1.5 py-0.5 rounded" style={{ fontSize: 11 }}>
                      {model.id}
                    </code>
                  </td>
                  <td className="px-5 py-3 text-gray-600" style={{ fontSize: 13 }}>
                    {(model.contextLength / 1000).toFixed(0)}K tokens
                  </td>
                  <td className="px-5 py-3 text-gray-600" style={{ fontSize: 13 }}>
                    ${model.costPer1kIn}/1K
                  </td>
                  <td className="px-5 py-3 text-gray-600" style={{ fontSize: 13 }}>
                    ${model.costPer1kOut}/1K
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Router Classifier */}
      <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
        <h3 className="text-gray-900 mb-4" style={{ fontWeight: 600 }}>Router Classifier</h3>
        <p className="text-gray-500 mb-4" style={{ fontSize: 13 }}>
          Test the NBFC router by classifying queries. API: POST /agent/router/classify
        </p>
        <div className="flex gap-3 mb-4">
          <input
            value={classifyInput}
            onChange={(e) => setClassifyInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleClassify()}
            placeholder="Enter a query to classify... (e.g., 'I want to close my loan')"
            className="flex-1 px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-lg outline-none focus:border-brand-main transition-colors"
            style={{ fontSize: 13 }}
          />
          <button
            onClick={handleClassify}
            disabled={isClassifying || !classifyInput.trim()}
            className="px-4 py-2.5 rounded-lg text-white flex items-center gap-2 disabled:opacity-50"
            style={{ background: "var(--brand-gradient)", fontSize: 13 }}
          >
            {isClassifying ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
            Classify
          </button>
        </div>

        {/* Quick test queries */}
        <div className="flex flex-wrap gap-2 mb-4">
          {[
            "I want to close my loan",
            "What's the processing fee?",
            "Tell me a joke",
            "Compare home loan vs LAP",
            "How to pay EMI?",
          ].map((q) => (
            <button
              key={q}
              onClick={() => { setClassifyInput(q); setClassifyResult(null); }}
              className="px-2.5 py-1 rounded-lg bg-gray-100 text-gray-600 hover:bg-gray-200 transition-colors"
              style={{ fontSize: 12 }}
            >
              {q}
            </button>
          ))}
        </div>

        {classifyResult && (
          <div className="bg-gray-50 rounded-xl p-4 border border-gray-200">
            <div className="grid sm:grid-cols-3 gap-4 mb-3">
              <div>
                <div className="text-gray-400" style={{ fontSize: 10 }}>CATEGORY</div>
                <div className="text-gray-900" style={{ fontSize: 14, fontWeight: 600 }}>
                  {classifyResult.category.replace(/_/g, " ")}
                </div>
              </div>
              <div>
                <div className="text-gray-400" style={{ fontSize: 10 }}>CONFIDENCE</div>
                <div className="flex items-center gap-2">
                  <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${classifyResult.confidence * 100}%`,
                        background: "var(--brand-gradient)",
                      }}
                    />
                  </div>
                  <span className="text-gray-900" style={{ fontSize: 13, fontWeight: 600 }}>
                    {(classifyResult.confidence * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
              <div>
                <div className="text-gray-400" style={{ fontSize: 10 }}>MODE</div>
                <div className="text-gray-900" style={{ fontSize: 14, fontWeight: 500 }}>{classifyResult.mode}</div>
              </div>
            </div>
            <div className="text-gray-600 border-t border-gray-200 pt-3" style={{ fontSize: 12 }}>
              {classifyResult.reasoning}
            </div>
          </div>
        )}
      </div>

      {/* GraphQL Section */}
      <div className="bg-white rounded-xl p-5 border border-gray-100 shadow-sm">
        <h3 className="text-gray-900 mb-2" style={{ fontWeight: 600 }}>GraphQL API</h3>
        <p className="text-gray-500 mb-4" style={{ fontSize: 13 }}>
          Access the full data API via GraphQL endpoint
        </p>
        <div className="bg-gray-900 rounded-lg p-4">
          <pre className="text-green-400" style={{ fontSize: 12 }}>
{`query {
  models {
    name
    models {
      id
      name
      contextLength
    }
  }
}`}
          </pre>
        </div>
        <p className="text-gray-400 mt-2" style={{ fontSize: 11 }}>
          Endpoint: GET/POST {"{base_url}"}/graphql
        </p>
      </div>
    </div>
  );
}
