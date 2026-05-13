import { useMutation } from "@tanstack/react-query";
import { sendClusterChatMessage } from "../api/clusters";

/**
 * Send a chat message to the cluster analytics co-pilot.
 * The component owns the chat history (React state) and passes it on each call.
 */
export const useClusterChat = (clusterId) =>
  useMutation({
    mutationFn: ({ message, history }) =>
      sendClusterChatMessage(clusterId, message, history),
  });
