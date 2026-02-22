import { create } from "zustand";
import { generateUUID } from "@/lib/uuid";

export interface KnxLogEntry {
  id: string;
  timestamp: string;
  type: "send" | "receive" | "error" | "info";
  address: string;
  value?: string;
  message?: string;
}

interface KnxLogStore {
  entries: KnxLogEntry[];
  addEntry: (entry: Omit<KnxLogEntry, "id" | "timestamp">) => void;
  clear: () => void;
}

const MAX_ENTRIES = 500;

export const useKnxLog = create<KnxLogStore>((set) => ({
  entries: [],
  addEntry: (entry) =>
    set((state) => ({
      entries: [
        {
          ...entry,
          id: generateUUID(),
          timestamp: new Date().toISOString(),
        },
        ...state.entries,
      ].slice(0, MAX_ENTRIES),
    })),
  clear: () => set({ entries: [] }),
}));
