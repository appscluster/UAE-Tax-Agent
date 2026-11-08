import { useEffect, useRef } from "react";
import * as d3 from "d3";
import { heldPhrase } from "./marks";

const BOUNDARY = 50_000_000;

function colorOf(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function shortName(name) {
  return name.replace(/ Trading LLC$/, "").replace(/ LLC$/, "");
}

function millions(value) {
  return `${d3.format(".3~s")(value).replace("G", "B").replace("M", "m")}`;
}

function marksOf(rows) {
  return rows.flatMap((row) => (row.marks || []).map((mark) => ({ ...mark })));
}

function heldCounts(marks, t) {
  const counts = new Map();
  marks.forEach((mark) => {
    if (mark.held) counts.set(heldPhrase(mark.held, t), (counts.get(heldPhrase(mark.held, t)) || 0) + 1);
    if (mark.auditor === "disagree") counts.set(t.plotDisagree, (counts.get(t.plotDisagree) || 0) + 1);
  });
  return [...counts.entries()].map(([label, count]) => ({ label, count })).sort((a, b) => b.count - a.count);
}

function usePlot(draw, deps) {
  const ref = useRef(null);
  useEffect(() => {
    const node = ref.current;
    if (!node) return undefined;
    const paint = () => draw(d3.select(node), node.clientWidth || 640);
    paint();
    const observer = new ResizeObserver(paint);
    observer.observe(node);
    return () => observer.disconnect();
  }, deps);
  return ref;
}

function paintAxis(axis, ink, line) {
  axis.selectAll("text").attr("fill", ink).attr("font-size", 12);
  axis.selectAll("line, path").attr("stroke", line);
}

function OutcomePlot({ rows, t }) {
  const ref = usePlot((svg, width) => {
    const data = rows.filter((row) => row.run_id).map((row) => ({
      name: shortName(row.legal_name),
      pass: row.pass_count || 0,
      verify: row.verify_count || 0,
    }));
    svg.selectAll("*").remove();
    const pass = colorOf("--pass");
    const verify = colorOf("--verify");
    const ink = colorOf("--ink");
    const ink2 = colorOf("--ink-2");
    const line = colorOf("--line");
    const margin = { top: 4, right: 56, bottom: 4, left: 128 };
    const row = 36;
    const height = margin.top + margin.bottom + data.length * row;
    const y = d3.scaleBand().domain(data.map((item) => item.name)).range([margin.top, height - margin.bottom]).padding(0.38);
    const peak = d3.max(data, (item) => item.pass + item.verify) || 1;
    const x = d3.scaleLinear().domain([0, peak]).range([margin.left, width - margin.right]);
    svg.attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img");
    const bands = svg.append("g").selectAll("g").data(data).join("g");
    bands.append("title").text((item) => `${item.name}. ${item.pass} ${t.pass}. ${item.verify} ${t.toVerify}.`);
    bands.append("rect")
      .attr("x", margin.left)
      .attr("y", (item) => y(item.name))
      .attr("width", (item) => Math.max(0, x(item.pass) - x(0)))
      .attr("height", y.bandwidth())
      .attr("fill", pass);
    bands.append("rect")
      .attr("x", (item) => x(item.pass))
      .attr("y", (item) => y(item.name))
      .attr("width", (item) => Math.max(0, x(item.pass + item.verify) - x(item.pass)))
      .attr("height", y.bandwidth())
      .attr("fill", verify);
    svg.append("g").selectAll("text").data(data).join("text")
      .attr("x", margin.left - 12)
      .attr("y", (item) => y(item.name) + y.bandwidth() / 2)
      .attr("dy", "0.35em")
      .attr("text-anchor", "end")
      .attr("fill", ink)
      .attr("font-size", 14)
      .text((item) => item.name);
    svg.append("g").selectAll("text").data(data).join("text")
      .attr("x", (item) => x(item.pass + item.verify) + 8)
      .attr("y", (item) => y(item.name) + y.bandwidth() / 2)
      .attr("dy", "0.35em")
      .attr("fill", ink2)
      .attr("font-size", 13)
      .text((item) => item.pass + item.verify);
    svg.append("line")
      .attr("x1", margin.left).attr("x2", margin.left)
      .attr("y1", margin.top).attr("y2", height - margin.bottom)
      .attr("stroke", line);
  }, [rows, t]);
  return <svg ref={ref} className="plot ltr" aria-label={t.plotOutcomes} />;
}

function HeldPlot({ rows, t }) {
  const ref = usePlot((svg, width) => {
    const items = heldCounts(marksOf(rows), t);
    svg.selectAll("*").remove();
    const verify = colorOf("--verify");
    const ink = colorOf("--ink");
    const line = colorOf("--line");
    const margin = { top: 4, right: 36, bottom: 28, left: 220 };
    const height = margin.top + margin.bottom + Math.max(items.length, 1) * 40;
    const y = d3.scaleBand().domain(items.map((item) => item.label)).range([margin.top, height - margin.bottom]).padding(0.4);
    const peak = d3.max(items, (item) => item.count) || 1;
    const x = d3.scaleLinear().domain([0, peak]).range([margin.left, width - margin.right]);
    svg.attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img");
    svg.append("g")
      .attr("transform", `translate(0,${height - margin.bottom})`)
      .call(d3.axisBottom(x).tickValues(d3.range(0, peak + 1)).tickFormat(d3.format("d")).tickSize(0).tickPadding(8))
      .call((axis) => paintAxis(axis, ink, line));
    svg.append("g").selectAll("rect").data(items).join("rect")
      .attr("x", margin.left)
      .attr("y", (item) => y(item.label))
      .attr("width", (item) => Math.max(2, x(item.count) - x(0)))
      .attr("height", y.bandwidth())
      .attr("fill", verify);
    svg.append("g").selectAll("text").data(items).join("text")
      .attr("x", margin.left - 12)
      .attr("y", (item) => y(item.label) + y.bandwidth() / 2)
      .attr("dy", "0.35em")
      .attr("text-anchor", "end")
      .attr("fill", ink)
      .attr("font-size", 14)
      .text((item) => item.label);
    svg.append("g").selectAll("text").data(items).join("text")
      .attr("x", (item) => x(item.count) + 8)
      .attr("y", (item) => y(item.label) + y.bandwidth() / 2)
      .attr("dy", "0.35em")
      .attr("fill", ink)
      .attr("font-size", 13)
      .text((item) => item.count);
  }, [rows, t]);
  return <svg ref={ref} className="plot ltr" aria-label={t.plotHeld} />;
}

function RevenuePlot({ rows, t }) {
  const ref = usePlot((svg, width) => {
    const companies = rows.map((row) => ({
      name: shortName(row.legal_name),
      value: row.stated_revenue_aed || 0,
    }));
    svg.selectAll("*").remove();
    const indigo = colorOf("--indigo");
    const ink = colorOf("--ink");
    const ink2 = colorOf("--ink-2");
    const line = colorOf("--line");
    const track = colorOf("--lavender");
    const margin = { top: 22, right: 48, bottom: 8, left: 128 };
    const height = margin.top + margin.bottom + companies.length * 40;
    const y = d3.scaleBand().domain(companies.map((company) => company.name)).range([margin.top, height - margin.bottom]).padding(0.4);
    const peak = Math.max(BOUNDARY, d3.max(companies, (company) => company.value) || 0);
    const x = d3.scaleLinear().domain([0, peak * 1.22]).range([margin.left, width - margin.right]);
    svg.attr("viewBox", `0 0 ${width} ${height}`).attr("role", "img");
    svg.append("g").selectAll("rect").data(companies).join("rect")
      .attr("x", margin.left)
      .attr("y", (company) => y(company.name))
      .attr("width", x(peak * 1.22) - x(0))
      .attr("height", y.bandwidth())
      .attr("fill", track);
    svg.append("g").selectAll("rect").data(companies).join("rect")
      .attr("x", margin.left)
      .attr("y", (company) => y(company.name))
      .attr("width", (company) => Math.max(0, x(company.value) - x(0)))
      .attr("height", y.bandwidth())
      .attr("fill", indigo);
    svg.append("line")
      .attr("x1", x(BOUNDARY)).attr("x2", x(BOUNDARY))
      .attr("y1", 18).attr("y2", height - margin.bottom)
      .attr("stroke", ink).attr("stroke-width", 1);
    svg.append("text")
      .attr("x", x(BOUNDARY)).attr("y", 12).attr("text-anchor", "middle")
      .attr("fill", ink).attr("font-size", 12).text(t.plotBoundary);
    svg.append("g").selectAll("text").data(companies).join("text")
      .attr("x", margin.left - 12)
      .attr("y", (company) => y(company.name) + y.bandwidth() / 2)
      .attr("dy", "0.35em")
      .attr("text-anchor", "end")
      .attr("fill", ink)
      .attr("font-size", 14)
      .text((company) => company.name);
    svg.append("g").selectAll("text").data(companies).join("text")
      .attr("x", (company) => x(company.value) + (Math.abs(company.value - BOUNDARY) < 1 ? 18 : 8))
      .attr("y", (company) => y(company.name) + y.bandwidth() / 2)
      .attr("dy", "0.35em")
      .attr("fill", ink2)
      .attr("font-size", 12)
      .text((company) => millions(company.value));
  }, [rows, t]);
  return <svg ref={ref} className="plot ltr" aria-label={t.plotRevenue} />;
}

export default function Plots({ rows, t }) {
  const list = rows || [];
  const ran = list.some((row) => row.run_id);
  const held = heldCounts(marksOf(list), t);
  return (
    <div className="plots">
      <figure>
        <figcaption>{t.plotOutcomes}</figcaption>
        <p className="legend">
          <span><span className="swatch is-pass" />{t.pass}</span>
          <span><span className="swatch is-verify" />{t.toVerify}</span>
        </p>
        {ran ? <OutcomePlot rows={list} t={t} /> : <p className="graph-edge">{t.plotEmpty}</p>}
      </figure>
      <figure>
        <figcaption>{t.plotHeld}</figcaption>
        {held.length ? <HeldPlot rows={list} t={t} /> : <p className="graph-edge">{t.plotEmpty}</p>}
      </figure>
      <figure>
        <figcaption>{t.plotRevenue}</figcaption>
        <RevenuePlot rows={list} t={t} />
        <p className="graph-edge plot-note">{t.plotAssertion}</p>
      </figure>
    </div>
  );
}
