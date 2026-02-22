import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchStatus, fetchGroupAddresses, sendKnxCommand, createGroupAddress, updateGroupAddress, deleteGroupAddress } from "@/services/knxApi";
import { KNXSendRequest, GroupAddressCreate, GroupAddress } from "@/types/knx";
import { useKnxLog } from "@/stores/knxLogStore";

export function useKnxStatus(refetchInterval = 5000) {
  return useQuery({
    queryKey: ["knx-status"],
    queryFn: fetchStatus,
    refetchInterval,
    retry: 1,
  });
}

export function useGroupAddresses() {
  return useQuery({
    queryKey: ["group-addresses"],
    queryFn: () => fetchGroupAddresses(),
    refetchInterval: 3000,
    retry: 1,
  });
}

export function useSendKnxCommand() {
  const qc = useQueryClient();
  const addLog = useKnxLog((s) => s.addEntry);
  return useMutation({
    mutationFn: (data: KNXSendRequest) => sendKnxCommand(data),
    onMutate: (data) => {
      addLog({ type: "send", address: data.address, value: String(data.value), message: `Sende ${data.value} auf ${data.address}` });
    },
    onSuccess: (_res, data) => {
      addLog({ type: "info", address: data.address, message: "Befehl erfolgreich gesendet" });
      setTimeout(() => qc.invalidateQueries({ queryKey: ["group-addresses"] }), 500);
    },
    onError: (err, data) => {
      addLog({ type: "error", address: data.address, message: err.message });
    },
  });
}

export function useCreateGroupAddress() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: GroupAddressCreate) => createGroupAddress(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["group-addresses"] }),
  });
}

export function useDeleteGroupAddress() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (address: string) => deleteGroupAddress(address),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["group-addresses"] }),
  });
}

export function useUpdateGroupAddress() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ address, data }: { address: string; data: Partial<GroupAddressCreate> }) =>
      updateGroupAddress(address, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["group-addresses"] }),
  });
}
