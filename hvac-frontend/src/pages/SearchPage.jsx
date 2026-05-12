import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import SearchView from "../components/SearchView";
import { useClusters } from "../hooks/useClusters";
import { asArray } from "../utils/format";

export default function SearchPage() {
  const navigate = useNavigate();
  const { data } = useClusters();

  const regions = useMemo(() => {
    const set = new Set();
    asArray(data).forEach((c) => {
      const arr = c.regions || (c.region ? [c.region] : []);
      arr.forEach((r) => r && set.add(r));
    });
    return Array.from(set).sort();
  }, [data]);

  return (
    <SearchView
      open
      mode="inline"
      onClose={() => navigate(-1)}
      onSelectCluster={(id) => navigate(`/themes/${id}`)}
      regions={regions}
    />
  );
}
