export interface CopyEnvironment {
  clipboard?: Pick<Clipboard, "writeText">;
  fallbackCopy: (text: string) => boolean;
}

function fallbackCopy(text: string): boolean {
  const activeElement =
    document.activeElement instanceof HTMLElement ? document.activeElement : null;
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.readOnly = true;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.append(textarea);
  textarea.select();
  textarea.setSelectionRange(0, text.length);
  const copied = document.execCommand("copy");
  textarea.remove();
  activeElement?.focus();
  return copied;
}

export async function copyText(
  text: string,
  environment: CopyEnvironment = {
    clipboard: navigator.clipboard,
    fallbackCopy,
  },
): Promise<void> {
  if (environment.clipboard) {
    try {
      await environment.clipboard.writeText(text);
      return;
    } catch {
      if (environment.fallbackCopy(text)) {
        return;
      }
      throw new Error("Clipboard write failed");
    }
  }

  if (!environment.fallbackCopy(text)) {
    throw new Error("Clipboard write failed");
  }
}
