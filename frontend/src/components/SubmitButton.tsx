"use client";

import { useFormStatus } from "react-dom";

type SubmitButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement>;

/** Submit button that disables itself while its form's Server Action runs. */
export function SubmitButton({ children, className = "", ...props }: SubmitButtonProps) {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className={`disabled:cursor-wait disabled:opacity-50 ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}
