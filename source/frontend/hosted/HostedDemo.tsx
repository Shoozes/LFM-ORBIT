import HostedEvidenceDemo from "./HostedEvidenceDemo";
import { useBrowserModel } from "./useBrowserModel";

export default function HostedDemo() {
  return <HostedEvidenceDemo model={useBrowserModel()} />;
}
