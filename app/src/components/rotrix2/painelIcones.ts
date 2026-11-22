// Rotrix L-1000 v2 — os ícones das teclas do Painel (tela e aparelho físico).
import type React from "react";
import {
  Play,
  LayoutGrid,
  FileText,
  Image as Imagem,
  Sun,
  Table,
  Globe,
  ArrowRight,
  ClipboardCheck,
  Sparkles,
  ScanSearch,
  Mic,
  Volume2,
  VolumeX,
  MessageCircle,
  Bot,
  ListChecks,
  Layers,
  Keyboard,
  Type,
  Lock,
  List,
  Folder,
  Music,
  Download,
  AppWindow,
  PenLine,
} from "lucide-react";
import type { Tecla } from "./painelComum";

export const ICONES: Record<string, React.ElementType> = {
  play: Play,
  grid: LayoutGrid,
  file: FileText,
  image: Imagem,
  sun: Sun,
  table: Table,
  globe: Globe,
  next: ArrowRight,
  clip: ClipboardCheck,
  spark: Sparkles,
  scan: ScanSearch,
  mic: Mic,
  vol: Volume2,
  mute: VolumeX,
  chat: MessageCircle,
  bot: Bot,
  check: ListChecks,
  layers: Layers,
  key: Keyboard,
  type: Type,
  lock: Lock,
  list: List,
  folder: Folder,
  media: Music,
  download: Download,
  rotrix: PenLine,
  app: AppWindow,
};

export const iconePadrao = (t: Tecla): string =>
  t.icone && ICONES[t.icone]
    ? t.icone
    : {
        programa: "app",
        site: "globe",
        rotrix: "rotrix",
        sistema: "vol",
        atalho: "key",
        texto: "type",
        expediente: "play",
        organizar: "grid",
      }[t.acao];

export const iconeDe = (t: Tecla): React.ElementType => ICONES[iconePadrao(t)] || AppWindow;
