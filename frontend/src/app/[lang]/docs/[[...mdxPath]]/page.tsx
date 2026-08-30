import { notFound } from "next/navigation";
import { generateStaticParamsFor, importPage } from "nextra/pages";

import { useMDXComponents as getMDXComponents } from "../../../../mdx-components";

export const generateStaticParams = generateStaticParamsFor("mdxPath", "lang");

function normalizeMdxPath(mdxPath: string[] | string | undefined) {
  if (Array.isArray(mdxPath)) {
    return mdxPath;
  }

  return mdxPath ? mdxPath.split("/") : [];
}

export async function generateMetadata(props) {
  const params = await props.params;
  const { metadata = { title: "", filePath: "" } } = await importPage(
    normalizeMdxPath(params.mdxPath),
    params.lang,
  );
  return metadata;
}

// eslint-disable-next-line @typescript-eslint/unbound-method
const Wrapper = getMDXComponents().wrapper;

export default async function Page(props) {
  const params = await props.params;
  const mdxPath = normalizeMdxPath(params.mdxPath);
  const result = await importPage(mdxPath, params.lang);

  const {
    default: MDXContent,
    toc = [],
    metadata = { title: "", filePath: "" },
    sourceCode = "",
  } = result;

  if (!MDXContent) {
    notFound();
  }

  return (
    <Wrapper toc={toc} metadata={metadata} sourceCode={sourceCode}>
      <MDXContent {...props} params={params} />
    </Wrapper>
  );
}
