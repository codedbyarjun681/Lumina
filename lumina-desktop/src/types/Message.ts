export interface MessageSource {
  original_filename: string;
  excerpt: string;
}

export interface Message {
  id?: string;
  role: "user" | "assistant";
  content: string;
  sources?: MessageSource[];
}
