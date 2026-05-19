interface AgentResult {
  agent: string;
  action: string;
  success: boolean;
  error?: { code: string; message: string };
}

function AgentIcon({ agent }: { agent: string }) {
  const icons: Record<string, string> = {
    dev: "\u{1F4BB}",
    content: "\u{1F4DD}",
    marketing: "\u{1F4CA}",
    commerce: "\u{1F4B0}",
  };
  return <span className="text-xl">{icons[agent] || "\u{1F916}"}</span>;
}

export default function AgentStatus({ results }: { results: AgentResult[] }) {
  if (results.length === 0) return null;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">
        Agent Results
      </h2>
      <div className="space-y-4">
        {results.map((result, i) => (
          <div
            key={`${result.agent}-${result.action}-${i}`}
            className={`p-4 rounded-lg border ${
              result.success
                ? "bg-green-50 border-green-200"
                : "bg-red-50 border-red-200"
            }`}
          >
            <div className="flex items-center gap-3">
              <AgentIcon agent={result.agent} />
              <div className="flex-1">
                <p className="font-medium text-gray-900 capitalize">
                  {result.agent}Agent - {result.action}
                </p>
                <p
                  className={`text-sm ${
                    result.success ? "text-green-600" : "text-red-600"
                  }`}
                >
                  {result.success ? "Completed" : `Failed: ${result.error?.message || "Unknown error"}`}
                </p>
              </div>
              <span
                className={`px-2 py-1 rounded text-xs font-medium ${
                  result.success
                    ? "bg-green-100 text-green-700"
                    : "bg-red-100 text-red-700"
                }`}
              >
                {result.success ? "SUCCESS" : "FAILED"}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
