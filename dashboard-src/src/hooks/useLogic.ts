import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchLogicBlocks,
  fetchLogicPages,
  fetchAvailableBlocks,
  fetchBlockPositions,
  saveBlockPositions,
  createLogicBlock,
  deleteLogicBlock,
  bindLogicBlock,
  unbindLogicBlock,
  setLogicBlockInput,
  triggerLogicBlock,
  createLogicPage,
  deleteLogicPage,
  fetchLogicBlockDebug,
  type BackendBlock,
  type BackendPage,
} from "@/services/knxApi";

export function useLogicBlocks() {
  return useQuery({
    queryKey: ["logic-blocks"],
    queryFn: fetchLogicBlocks,
    refetchInterval: 3000,
  });
}

export function useLogicPages() {
  return useQuery({
    queryKey: ["logic-pages"],
    queryFn: fetchLogicPages,
    refetchInterval: 10000,
  });
}

export function useAvailableBlocks() {
  return useQuery({
    queryKey: ["logic-available-blocks"],
    queryFn: fetchAvailableBlocks,
  });
}

export function useBlockPositions() {
  return useQuery({
    queryKey: ["logic-positions"],
    queryFn: fetchBlockPositions,
  });
}

export function useBlockDebug(instanceId: string | null) {
  return useQuery({
    queryKey: ["logic-block-debug", instanceId],
    queryFn: () => fetchLogicBlockDebug(instanceId!),
    enabled: !!instanceId,
    refetchInterval: 2000,
  });
}

export function useCreateBlock() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ blockType, pageId }: { blockType: string; pageId?: string }) =>
      createLogicBlock(blockType, pageId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["logic-blocks"] }),
  });
}

export function useDeleteBlock() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (instanceId: string) => deleteLogicBlock(instanceId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["logic-blocks"] }),
  });
}

export function useBindBlock() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ instanceId, data }: { instanceId: string; data: { input_key?: string; output_key?: string; address: string } }) =>
      bindLogicBlock(instanceId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["logic-blocks"] }),
  });
}

export function useUnbindBlock() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ instanceId, data }: { instanceId: string; data: { input_key?: string; output_key?: string } }) =>
      unbindLogicBlock(instanceId, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["logic-blocks"] }),
  });
}

export function useSetBlockInput() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ instanceId, inputKey, value }: { instanceId: string; inputKey: string; value: string }) =>
      setLogicBlockInput(instanceId, inputKey, value),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["logic-blocks"] }),
  });
}

export function useTriggerBlock() {
  return useMutation({
    mutationFn: (instanceId: string) => triggerLogicBlock(instanceId),
  });
}

export function useCreatePage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ name, pageId }: { name: string; pageId?: string }) =>
      createLogicPage(name, pageId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["logic-pages"] }),
  });
}

export function useDeletePage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (pageId: string) => deleteLogicPage(pageId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["logic-pages"] });
      qc.invalidateQueries({ queryKey: ["logic-blocks"] });
    },
  });
}

export function useSavePositions() {
  return useMutation({
    mutationFn: (positions: Record<string, { x: number; y: number }>) =>
      saveBlockPositions(positions),
  });
}
