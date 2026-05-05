import { useMutation, useQueryClient } from "@tanstack/react-query";
import { uploadCSV } from "../api/complaints";

export const useUploadCSV = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: uploadCSV,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["clusters"] });
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
};
