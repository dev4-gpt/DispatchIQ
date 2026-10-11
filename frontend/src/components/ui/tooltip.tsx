import * as Primitive from "@radix-ui/react-tooltip";
import type { ReactElement, ReactNode } from "react";

export function Tooltip({
  children,
  content,
}: {
  children: ReactElement;
  content: ReactNode;
}) {
  return (
    <Primitive.Provider delayDuration={250}>
      <Primitive.Root>
        <Primitive.Trigger asChild>{children}</Primitive.Trigger>
        <Primitive.Portal>
          <Primitive.Content
            className="product-tooltip"
            sideOffset={7}
            collisionPadding={12}
          >
            {content}
            <Primitive.Arrow className="tooltip-arrow" />
          </Primitive.Content>
        </Primitive.Portal>
      </Primitive.Root>
    </Primitive.Provider>
  );
}
