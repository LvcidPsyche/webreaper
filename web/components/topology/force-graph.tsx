'use client';

import { useRef, useEffect } from 'react';
import * as d3 from 'd3';
import type { TopologyData, TopologyNode, TopologyLink } from '@/lib/types';

interface ForceGraphProps {
  data: TopologyData;
  width?: number;
  height?: number;
}

interface SimNode extends TopologyNode, d3.SimulationNodeDatum {}
interface SimLink extends d3.SimulationLinkDatum<SimNode> {
  weight: number;
}

export function ForceGraph({ data, width = 800, height = 500 }: ForceGraphProps) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || !data.nodes.length) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll('*').remove();

    const nodes: SimNode[] = data.nodes.map((n) => ({ ...n }));
    const nodeMap = new Map(nodes.map((n) => [n.id, n]));
    const links: SimLink[] = data.links
      .filter((l) => nodeMap.has(l.source) && nodeMap.has(l.target))
      .map((l) => ({ source: l.source, target: l.target, weight: l.weight }));

    const simulation = d3
      .forceSimulation(nodes)
      .force('link', d3.forceLink<SimNode, SimLink>(links).id((d) => d.id).distance(80))
      .force('charge', d3.forceManyBody().strength(-200))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(20));

    const g = svg.append('g');

    svg.call(
      d3.zoom<SVGSVGElement, unknown>().scaleExtent([0.3, 3]).on('zoom', (event) => {
        g.attr('transform', event.transform);
      }) as never
    );

    const link = g
      .append('g')
      .selectAll('line')
      .data(links)
      .join('line')
      .attr('stroke', '#1e1e2e')
      .attr('stroke-width', (d) => Math.max(1, d.weight * 0.5));

    const node = g
      .append('g')
      .selectAll('circle')
      .data(nodes)
      .join('circle')
      .attr('r', (d) => Math.max(4, Math.min(12, d.pages * 0.5)))
      .attr('fill', '#00d4ff')
      .attr('fill-opacity', 0.7)
      .attr('stroke', '#00d4ff')
      .attr('stroke-width', 1)
      .attr('stroke-opacity', 0.3)
      .call(
        d3
          .drag<SVGCircleElement, SimNode>()
          .on('start', (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on('drag', (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on('end', (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          }) as unknown as (selection: d3.Selection<SVGCircleElement | d3.BaseType, SimNode, SVGGElement, unknown>) => void
      );

    const label = g
      .append('g')
      .selectAll('text')
      .data(nodes)
      .join('text')
      .text((d) => d.domain)
      .attr('font-size', 9)
      .attr('font-family', 'monospace')
      .attr('fill', '#666680')
      .attr('dx', 14)
      .attr('dy', 3);

    node.append('title').text((d) => `${d.domain} (${d.pages} pages)`);

    simulation.on('tick', () => {
      link
        .attr('x1', (d) => (d.source as SimNode).x!)
        .attr('y1', (d) => (d.source as SimNode).y!)
        .attr('x2', (d) => (d.target as SimNode).x!)
        .attr('y2', (d) => (d.target as SimNode).y!);
      node.attr('cx', (d) => d.x!).attr('cy', (d) => d.y!);
      label.attr('x', (d) => d.x!).attr('y', (d) => d.y!);
    });

    return () => { simulation.stop(); };
  }, [data, width, height]);

  return (
    <svg
      ref={svgRef}
      width={width}
      height={height}
      className="bg-reaper-bg rounded-lg border border-reaper-border"
    />
  );
}
