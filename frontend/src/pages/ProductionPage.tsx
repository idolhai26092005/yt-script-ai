import type { useProductionFlow } from '../hooks/useProductionFlow';
import { SingleOutputPanel } from './SingleOutputPanel';

interface ProductionPageProps {
  apiKey: string;
  modelName: string;
  prodFlow: ReturnType<typeof useProductionFlow>;
  onBack: () => void;
}

// Legacy-route guard: /generate remains available for old navigation paths, but
// the real production surface now lives inside the Single workflow component.
export default function ProductionPage({
  apiKey,
  modelName,
  prodFlow,
  onBack,
}: ProductionPageProps) {
  return (
    <section className="single-page" aria-label="Output video đơn">
      <SingleOutputPanel
        apiKey={apiKey}
        modelName={modelName}
        prodFlow={prodFlow}
        autoStart
        onBack={onBack}
        backLabel="Quay lại"
      />
    </section>
  );
}
