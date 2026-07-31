import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MarkdownMessage } from "./MarkdownMessage";

describe("MarkdownMessage", () => {
  it("renders common Markdown without exposing formatting markers", () => {
    render(<MarkdownMessage content={"### Hồ sơ\n- **Khai sinh**\n- Dùng `PDF`\n\nXem [nguồn chính thức](https://example.test/source)."} />);

    expect(screen.getByRole("heading", { name: "Hồ sơ" })).toBeInTheDocument();
    expect(screen.getByText("Khai sinh").tagName).toBe("STRONG");
    expect(screen.getByText("PDF").tagName).toBe("CODE");
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByRole("link", { name: "nguồn chính thức" })).toHaveAttribute("href", "https://example.test/source");
    expect(screen.queryByText("**Khai sinh**")).not.toBeInTheDocument();
  });

  it("treats HTML as text instead of injecting it", () => {
    const { container } = render(<MarkdownMessage content={'<img src=x onerror="alert(1)">'} />);
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByText('<img src=x onerror="alert(1)">')).toBeInTheDocument();
  });
});
