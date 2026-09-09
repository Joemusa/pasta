import { NEWS_SOURCES } from "@/lib/intelligence/demo-data";
import { publicXStatus } from "@/lib/intelligence/x-config";
import { SettingsView } from "./settings-view";

export const dynamic = "force-dynamic";

export default function SettingsPage() {
  return <SettingsView sources={NEWS_SOURCES} initialXStatus={publicXStatus()} />;
}
